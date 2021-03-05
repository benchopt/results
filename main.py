import matplotlib

from pathlib import Path

from benchopt.plotting.generate_html import plot_benchmark_html_all

matplotlib.use('Agg')

ROOT = Path(__file__).parent

if __name__ == "__main__":
    plot_benchmark_html_all(["--root", ROOT])
