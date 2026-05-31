#!/usr/bin/env python3
import argparse
import csv
import matplotlib.pyplot as plt
import os

# Premium modern color palette
COLORS = [
    "#3b82f6", # Vibrant Blue
    "#ec4899", # Pink/Magenta
    "#10b981", # Emerald Green
    "#f59e0b", # Amber/Orange
    "#8b5cf6", # Purple
    "#ef4444", # Red
    "#06b6d4"  # Cyan
]

def load_data(csv_path):
    loads = []
    latencies = []
    statuses = []
    with open(csv_path, mode='r') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        # Verify columns exist
        if "Load" not in header or "Average_Latency" not in header or "Status" not in header:
            raise ValueError(f"CSV file {csv_path} is missing required columns (Load, Average_Latency, Status).")
            
        load_idx = header.index("Load")
        lat_idx = header.index("Average_Latency")
        status_idx = header.index("Status")
        
        for row in reader:
            if not row:
                continue
            loads.append(float(row[load_idx]))
            statuses.append(row[status_idx])
            try:
                latencies.append(float(row[lat_idx]))
            except ValueError:
                latencies.append(float('inf'))
    return loads, latencies, statuses

def main():
    parser = argparse.ArgumentParser(
        description="Plot premium, publication-quality NoC load-latency curves from generated CSV data."
    )
    parser.add_argument("csv_files", nargs="+", help="One or more CSV result files to plot.")
    parser.add_argument("--output", "-o", type=str, default="load_latency_plot.png", help="Path to save the generated plot image.")
    parser.add_argument("--title", type=str, default="NoC Load-Latency Curve", help="Title of the plot.")
    parser.add_argument("--no-sat-lines", action="store_true", help="Disable drawing vertical lines for saturation boundaries.")
    args = parser.parse_args()

    # Premium style configuration
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=150)
    
    # Light grid lines
    ax.grid(True, linestyle="--", linewidth=0.5, color="#e2e8f0", zorder=0)
    ax.set_facecolor("#f8fafc")
    
    # Hide top and right spines
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")

    for idx, csv_path in enumerate(args.csv_files):
        if not os.path.exists(csv_path):
            print(f"Warning: File {csv_path} not found. Skipping.")
            continue
            
        try:
            loads, latencies, statuses = load_data(csv_path)
        except Exception as e:
            print(f"Error loading {csv_path}: {e}. Skipping.")
            continue
        
        # Find baseline latency (latency at minimum load)
        sorted_points = sorted(zip(loads, latencies, statuses), key=lambda x: x[0])
        baseline_lat = 8.0
        for l, lat, status in sorted_points:
            if status == "success" and lat != float('inf'):
                baseline_lat = lat
                break
                
        # Separate success and timeout/fail data
        succ_loads = []
        succ_latencies = []
        timeout_loads = []
        
        for l, lat, status in zip(loads, latencies, statuses):
            if status in ["success", "saturated"] and lat < 10.0 * baseline_lat:
                succ_loads.append(l)
                succ_latencies.append(lat)
            else:
                timeout_loads.append(l)
                
        if not succ_loads:
            print(f"Warning: No successful data points in {csv_path}. Skipping.")
            continue
            
        color = COLORS[idx % len(COLORS)]
        label = os.path.basename(csv_path).replace(".csv", "").replace("_latency", "")
        
        # Plot curve
        ax.plot(
            succ_loads, 
            succ_latencies, 
            label=label, 
            color=color, 
            linewidth=2.5, 
            marker='o', 
            markersize=6, 
            markerfacecolor='white',
            markeredgewidth=1.5,
            markeredgecolor=color,
            zorder=3
        )
        
        # Draw saturation vertical line if any timeouts detected
        # A true saturation point must not have any successful runs at higher loads (to filter out transient noise)
        true_sat_loads = [l for l in timeout_loads if not any(succ_l > l for succ_l in succ_loads)]
        if true_sat_loads and not args.no_sat_lines:
            sat_load = min(true_sat_loads)
            ax.axvline(
                x=sat_load, 
                color=color, 
                linestyle=":", 
                linewidth=1.5, 
                alpha=0.8,
                label=f"{label} Saturation Limit ({sat_load:.2f})",
                zorder=2
            )
            
    ax.set_title(args.title, fontsize=14, fontweight="bold", pad=15, color="#1e293b")
    ax.set_xlabel("Offered Load (injection rate)", fontsize=11, fontweight="semibold", labelpad=10, color="#334155")
    ax.set_ylabel("Average Latency (clock cycles)", fontsize=11, fontweight="semibold", labelpad=10, color="#334155")
    
    # Legend styling
    ax.legend(
        loc="upper left",
        frameon=True,
        facecolor="white",
        edgecolor="#e2e8f0",
        fontsize=9,
        title="Topologies",
        title_fontsize=10
    )
    
    # Tick label styling
    ax.tick_params(colors="#475569", labelsize=9)
    
    plt.tight_layout()
    
    # Save the figure
    plt.savefig(args.output, dpi=300, facecolor="white")
    print(f"Plot successfully saved to: {os.path.abspath(args.output)}")

if __name__ == "__main__":
    main()
