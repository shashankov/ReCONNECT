#!/usr/bin/env python3
import argparse
import subprocess
import re
import csv
import sys
import os

def parse_args():
    parser = argparse.ArgumentParser(
        description="Smart, sample-efficient load-latency curve generator for NoC simulation."
    )
    
    # Topology and simulation parameters
    parser.add_argument("--topology", type=str, default="router", help="NoC topology (router, ring, double_ring, mesh, torus, directional_torus, butterfly)")
    parser.add_argument("--num-inputs", type=int, default=4, help="Number of inputs (ports)")
    parser.add_argument("--num-outputs", type=int, default=4, help="Number of outputs (ports)")
    parser.add_argument("--num-rows", type=int, default=2, help="Number of rows (for mesh/torus/dtorus)")
    parser.add_argument("--num-cols", type=int, default=2, help="Number of columns (for mesh/torus/dtorus)")
    parser.add_argument("-k", type=int, default=2, help="K parameter (for butterfly)")
    parser.add_argument("-n", type=int, default=2, help="N parameter (for butterfly)")
    parser.add_argument("--packet-count", "--packet-count-init", type=int, dest="packet_count_init", default=8192, help="Packet count for initial space exploration sweep.")
    parser.add_argument("--packet-count-final", type=int, default=65536, help="Packet count for final high-accuracy run of selected points. If equal to initial, final run is skipped.")
    
    # Additional microarchitecture / link parameters
    parser.add_argument("--serialization-factor", type=int, default=1, help="Serialization factor")
    parser.add_argument("--clkcross-factor", type=int, default=1, help="Clock crossing factor")
    parser.add_argument("--pipeline-links", type=int, default=0, help="Pipeline links")
    parser.add_argument("--extra-pipeline-long-links", type=int, default=0, help="Extra pipeline long links")
    parser.add_argument("--flit-buffer-depth", type=int, default=8, help="Flit buffer depth")
    parser.add_argument("--packet-length", type=int, default=None, help="Packet length in flits (defaults to half the flit buffer depth)")
    
    # Sweep control
    parser.add_argument("--budget", type=int, default=20, help="Maximum number of load points to sample")
    parser.add_argument("--min-resolution", type=float, default=0.01, help="Minimum load interval size to refine")
    parser.add_argument("--output", type=str, default="load_latency.csv", help="Output CSV path")
    parser.add_argument("--skip-compile", action="store_true", help="Skip the compilation step")
    parser.add_argument("--sat-threshold", type=float, default=0.97, help="Efficiency threshold (received throughput / offered load) below which network is considered saturated.")
    
    return parser.parse_args()

def compile_simulation(args, packet_count):
    print(f"--- Compiling simulation binary using Makefile (PACKET_COUNT={packet_count}) ---")
    make_cmd = [
        "make", "obj_dir/Vgeneric_harness_tb_sim",
        f"TOPOLOGY={args.topology}",
        f"NUM_INPUTS={args.num_inputs}",
        f"NUM_OUTPUTS={args.num_outputs}",
        f"NUM_ROWS={args.num_rows}",
        f"NUM_COLS={args.num_cols}",
        f"K={args.k}",
        f"N={args.n}",
        f"PACKET_COUNT={packet_count}",
        f"SERIALIZATION_FACTOR={args.serialization_factor}",
        f"CLKCROSS_FACTOR={args.clkcross_factor}",
        f"PIPELINE_LINKS={args.pipeline_links}",
        f"EXTRA_PIPELINE_LONG_LINKS={args.extra_pipeline_long_links}",
        f"FLIT_BUFFER_DEPTH={args.flit_buffer_depth}",
        f"PACKET_LENGTH={args.packet_length}"
    ]
    print("Running command:", " ".join(make_cmd))
    res = subprocess.run(make_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Compilation failed!", file=sys.stderr)
        print("stdout:", res.stdout, file=sys.stderr)
        print("stderr:", res.stderr, file=sys.stderr)
        sys.exit(1)
    print("Compilation successful.")

def run_simulation(load_val):
    cmd = ["./obj_dir/Vgeneric_harness_tb_sim", f"+LOAD={load_val}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    stdout = res.stdout
    
    success = "TEST PASSED" in stdout
    timeout = "Timeout!" in stdout or not success
    
    # Extract latency, throughput
    pattern = re.compile(
        r"Id:\s*(\d+),\s*Total Recv Count:\s*(\d+),\s*Average latency:\s*([\d\.]+),\s*Throughput:\s*([\d\.]+|undef)"
    )
    matches = pattern.findall(stdout)
    
    if not matches:
        return {
            "load": load_val,
            "latency": float('inf'),
            "throughput": 0.0,
            "status": "failed",
            "log": stdout
        }
        
    total_recv = 0
    weighted_latency_sum = 0.0
    total_throughput = 0.0
    
    for match in matches:
        count = int(match[1])
        latency = float(match[2])
        thr_str = match[3]
        thr = float(thr_str) if thr_str != 'undef' else 0.0
        
        total_recv += count
        weighted_latency_sum += latency * count
        total_throughput += thr
        
    avg_latency = weighted_latency_sum / total_recv if total_recv > 0 else float('inf')
    
    if timeout:
        return {
            "load": load_val,
            "latency": float('inf'),
            "throughput": total_throughput,
            "status": "timeout"
        }
        
    return {
        "load": load_val,
        "latency": avg_latency,
        "throughput": total_throughput,
        "status": "success"
    }

def write_csv(filename, results):
    sorted_loads = sorted(results.keys())
    print(f"--- Saving results to {filename} ---")
    with open(filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Load", "Average_Latency", "Status"])
        for load in sorted_loads:
            res = results[load]
            writer.writerow([
                f"{res['load']:.4f}",
                f"{res['latency']:.6f}" if res['latency'] != float('inf') else "inf",
                res['status']
            ])
    print(f"Successfully wrote {len(sorted_loads)} data points to {filename}")

def main():
    args = parse_args()
    
    if args.packet_length is None:
        args.packet_length = args.flit_buffer_depth // 2

    if not args.skip_compile:
        compile_simulation(args, args.packet_count_init)
    else:
        if not os.path.exists("./obj_dir/Vgeneric_harness_tb_sim"):
            print("Error: Compiled simulation binary not found at ./obj_dir/Vgeneric_harness_tb_sim. Run without --skip-compile first.", file=sys.stderr)
            sys.exit(1)
            
    # Dictionary to keep track of all results (load -> result dict)
    results = {}
    
    # Helper to run and cache simulation
    def evaluate(load_val):
        load_val = round(load_val, 4)
        if load_val in results:
            return results[load_val]
        print(f"Running simulation at Load = {load_val:.4f}...", end="", flush=True)
        res = run_simulation(load_val)
        
        # Throughput efficiency and latency check for saturation
        efficiency = 1.0
        if res["status"] == "success":
            # Always calculate efficiency first
            expected_throughput = args.num_inputs * load_val
            if expected_throughput > 0:
                efficiency = res["throughput"] / expected_throughput
                
            # 10x baseline latency check
            baseline_key = 0.02
            if baseline_key in results and results[baseline_key]["status"] == "success":
                baseline_lat = results[baseline_key]["latency"]
                if res["latency"] >= 10.0 * baseline_lat:
                    res["status"] = "saturated"
            
            # Throughput efficiency check
            if res["status"] == "success" and efficiency < args.sat_threshold:
                res["status"] = "saturated"
                    
        results[load_val] = res
        if res["status"] == "success":
            print(f" Success (Latency = {res['latency']:.2f}, Eff = {efficiency:.2%})")
        elif res["status"] == "saturated":
            print(f" Saturated (Latency = {res['latency']:.2f}, Eff = {efficiency:.2%})")
        else:
            print(f" {res['status'].upper()}")
        return res

    # Phase 0: Baseline Evaluation
    print("--- Phase 0: Baseline Evaluation ---")
    evaluate(0.02)
    
    # Phase 1: Binary search to find saturation limit L_sat
    print("--- Phase 1: Saturation Limit Detection (Binary Search) ---")
    low = 0.01
    high = 1.00
    L_sat = 1.00
    
    # We run 5 steps of binary search
    for step in range(5):
        mid = (low + high) / 2
        res = evaluate(mid)
        if res["status"] == "success":
            low = mid
            L_sat = max(L_sat, mid)
        else:
            high = mid
            
    successful_loads = [l for l, r in results.items() if r["status"] == "success"]
    if successful_loads:
        L_sat = max(successful_loads)
    else:
        L_sat = 0.1
        
    print(f"Saturation load limit detected near: {L_sat:.4f}")
    
    # Phase 2: Initial Grid Sampling
    print("--- Phase 2: Initial Grid Sampling ---")
    # Sample points at 10%, 30%, 50%, 70%, 85%, 95% of L_sat
    grid_factors = [0.1, 0.3, 0.5, 0.7, 0.85, 0.95]
    for factor in grid_factors:
        target_load = factor * L_sat
        if any(abs(l - target_load) < 0.02 for l in results):
            continue
        evaluate(target_load)
        
    # Also evaluate a point near 0.02 to establish baseline if not already done
    if not any(l < 0.04 for l in results):
        evaluate(0.02)
        
    # Phase 3: Adaptive Refinement
    print("--- Phase 3: Adaptive Refinement (Smart Sweep) ---")
    while len(results) < args.budget:
        sorted_success = sorted(
            [r for r in results.values() if r["status"] == "success"],
            key=lambda x: x["load"]
        )
        
        if len(sorted_success) < 2:
            break
            
        best_score = -1.0
        best_interval_idx = -1
        
        for i in range(len(sorted_success) - 1):
            p1 = sorted_success[i]
            p2 = sorted_success[i+1]
            
            dl = p2["load"] - p1["load"]
            dy = p2["latency"] - p1["latency"]
            
            if dl < args.min_resolution:
                continue
                
            new_load = round((p1["load"] + p2["load"]) / 2, 4)
            if new_load in results:
                continue
                
            # Score is based on delta_latency * delta_load
            score = dy * dl
            
            if score > best_score:
                best_score = score
                best_interval_idx = i
                
        # If no interval can be refined
        if best_interval_idx == -1 or best_score <= 0.0:
            print("No further intervals to refine or resolution limit reached.")
            break
            
        p1 = sorted_success[best_interval_idx]
        p2 = sorted_success[best_interval_idx + 1]
        new_load = (p1["load"] + p2["load"]) / 2
        
        print(f"Refining interval [{p1['load']:.4f}, {p2['load']:.4f}] (score = {best_score:.4f})")
        evaluate(new_load)
        
    # Phase 4: Final High-Accuracy Re-evaluation
    if args.packet_count_final != args.packet_count_init and not args.skip_compile:
        print("--- Phase 4: Final Re-evaluation with High-Accuracy Packet Count ---")
        compile_simulation(args, args.packet_count_final)
        
        final_results = {}
        
        # Evaluate baseline first for final high-accuracy run
        print("Re-running simulation for Load = 0.0200 with final packet count...", end="", flush=True)
        baseline_res = run_simulation(0.02)
        final_baseline_lat = baseline_res["latency"] if baseline_res["status"] == "success" else 8.0
        if baseline_res["status"] == "success":
            print(f" Success (Latency = {baseline_res['latency']:.2f}, Eff = {baseline_res['throughput'] / (args.num_inputs * 0.02):.2%})")
        else:
            print(f" {baseline_res['status'].upper()}")
        final_results[0.02] = baseline_res
        
        sorted_loads = sorted(results.keys())
        for load_val in sorted_loads:
            if load_val == 0.02:
                continue
            print(f"Re-running simulation for Load = {load_val:.4f} with final packet count...", end="", flush=True)
            res = run_simulation(load_val)
            
            efficiency = 1.0
            if res["status"] == "success":
                # Always calculate efficiency first
                expected_throughput = args.num_inputs * load_val
                if expected_throughput > 0:
                    efficiency = res["throughput"] / expected_throughput
                    
                # 10x baseline latency check
                if res["latency"] >= 10.0 * final_baseline_lat:
                    res["status"] = "saturated"
                
                # Throughput efficiency check
                if res["status"] == "success" and efficiency < args.sat_threshold:
                    res["status"] = "saturated"
                        
            final_results[load_val] = res
            if res["status"] == "success":
                print(f" Success (Latency = {res['latency']:.2f}, Eff = {efficiency:.2%})")
            elif res["status"] == "saturated":
                print(f" Saturated (Latency = {res['latency']:.2f}, Eff = {efficiency:.2%})")
            else:
                print(f" {res['status'].upper()}")
        results = final_results
        
    # Write to CSV
    write_csv(args.output, results)

if __name__ == "__main__":
    main()
