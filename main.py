import shutil
from pathlib import Path
from datetime import datetime
import glob

import click
from mako.template import Template
import matplotlib
import matplotlib.pyplot as plt

import pandas as pd

from benchopt.constants import PLOT_KINDS
from benchopt.plotting import plot_histogram  # noqa: F401
from benchopt.plotting import plot_objective_curve  # noqa: F401
from benchopt.plotting import plot_suboptimality_curve  # noqa: F401
from benchopt.plotting import plot_relative_suboptimality_curve  # noqa: F401 E501


matplotlib.use('Agg')

ROOT = Path(__file__).parent
BUILD_DIR = Path(__file__).parent / "build"
BUILD_DIR_OUTPUTS = BUILD_DIR / "outputs"
BUILD_DIR_FIGURES = BUILD_DIR / "figures"

TEMPLATE_INDEX = ROOT / "templates" / "index.mako.html"
TEMPLATE_BENCHMARK = ROOT / "templates" / "benchmark.mako.html"
TEMPLATE_RESULT = ROOT / "templates" / "result.mako.html"


def generate_plot_benchmark(fname, kinds=PLOT_KINDS):
    """Generate all possible plots for a given benchmark.

    Parameters
    ----------
    fname : instance of pandas.DataFrame
        The benchmark results.
    kinds : list of str
        List of the kind of plots that will be generated. This needs to be a
        sub-list of PLOT_KINDS.keys().

    Returns
    -------
    figs : list
        The matplotlib figures for convergence curve and histogram
        for each dataset.
    """

    df = pd.read_csv(fname)
    dataset_names = df['data_name'].unique()
    objective_names = df['objective_name'].unique()
    fname_short = fname.replace('outputs/', '').replace('/', '_')

    figures = {}
    n_figure = 0
    for data_name in dataset_names:
        figures[data_name] = {}
        df_data = df[df['data_name'] == data_name]
        for objective_name in objective_names:
            figures[data_name][objective_name] = {}
            df_obj = df_data[df_data['objective_name'] == objective_name]

            for k in kinds:
                if k not in PLOT_KINDS:
                    raise ValueError(
                        f"Requesting invalid plot '{k}'. Should be in:\n"
                        f"{PLOT_KINDS}")
                plot_func = globals()[PLOT_KINDS[k]]
                try:
                    fig = plot_func(df_obj, plotly=True)
                except TypeError:
                    fig = plot_func(df_obj)

                figures[data_name][objective_name][k] = export_figure(
                    fig, f"{fname_short}_{n_figure}"
                )
                n_figure += 1

    return dict(
        figures=figures, dataset_names=dataset_names, fname_short=fname_short,
        objective_names=objective_names, kinds=kinds.keys()
    )


def export_figure(fig, fig_name):
    if hasattr(fig, 'to_html'):
        return fig.to_html(include_plotlyjs=False)

    fig_basename = f"{fig_name}.svg"
    save_name = BUILD_DIR_FIGURES / fig_basename
    fig.savefig(save_name)
    plt.close(fig)
    return f'figures/{fig_basename}'


def get_results(fnames):
    results = []
    BUILD_DIR_OUTPUTS.mkdir(exist_ok=True, parents=True)
    BUILD_DIR_FIGURES.mkdir(exist_ok=True, parents=True)

    for fname in fnames:
        print(f"Processing {fname}")
        fname_no_output = fname.replace('outputs/', '')
        fname_no_output_path = Path(fname_no_output)

        # Copy CSV
        shutil.copy(fname, BUILD_DIR_OUTPUTS / fname_no_output_path)

        df = pd.read_csv(fname)
        datasets = list(df['data_name'].unique())

        # Generate figures
        result = dict(
            fname=fname,
            datasets=datasets,
            **generate_plot_benchmark(fname)
        )
        results.append(result)

    for result in results:
        result['page'] = \
            f"{result['fname_short'].replace('.csv', '.html')}"

    return results


def render_benchmark(results, benchmark):
    return Template(filename=str(TEMPLATE_BENCHMARK),
                    input_encoding="utf-8").render(
        results=results,
        benchmark=benchmark,
        max_rows=15,
        nb_total_benchs=len(results),
        last_updated=datetime.now(),
    )


def render_index(benchmarks):
    return Template(filename=str(TEMPLATE_INDEX),
                    input_encoding="utf-8").render(
        benchmarks=benchmarks,
        nb_total_benchs=len(benchmarks),
        max_rows=15,
        last_updated=datetime.now(),
    )


def copy_static():
    dst = BUILD_DIR / 'static'
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / 'static', dst)


def render_all_results(results, benchmark):
    htmls = []
    for result in results:
        html = Template(
            filename=str(TEMPLATE_RESULT),
            input_encoding="utf-8").render(
            result=result,
            benchmark=benchmark,
        )
        htmls.append(html)
    return htmls


@click.command()
@click.option('--pattern', '-k', 'patterns',
              metavar="<pattern>", multiple=True, type=str,
              help="Include results matching <pattern>.")
@click.option('--benchmark', '-b', 'benchmarks',
              metavar="<pattern>", multiple=True, type=str,
              help="benchmarks to include.")
def main(patterns=(), benchmarks=()):
    if not benchmarks:
        benchmarks = [
            f.name for f in (ROOT / 'outputs').iterdir() if f.is_dir()
        ]
    if not patterns:
        patterns = ['*']

    copy_static()

    rendered = render_index(benchmarks)
    index_filename = BUILD_DIR / 'index.html'
    print(f"Writing index to {index_filename}")
    with open(index_filename, "w") as f:
        f.write(rendered)

    for benchmark in benchmarks:
        print(f'Rendering benchmark: {benchmark}')

        Path(BUILD_DIR / benchmark).mkdir(exist_ok=True)
        Path(BUILD_DIR_FIGURES / benchmark).mkdir(exist_ok=True, parents=True)
        Path(BUILD_DIR_OUTPUTS / benchmark).mkdir(exist_ok=True, parents=True)

        fnames = []
        for p in patterns:
            fnames += glob.glob(f'outputs/{benchmark}/{p}.csv')
        fnames = sorted(set(fnames))
        results = get_results(fnames)
        rendered = render_benchmark(results, benchmark)

        benchmark_filename = BUILD_DIR / f"{benchmark}.html"
        print(f"Writing {benchmark} results to {benchmark_filename}")
        with open(benchmark_filename, "w") as f:
            f.write(rendered)

        htmls = render_all_results(results, benchmark)
        for result, html in zip(results, htmls):
            result_filename = BUILD_DIR / result['page']
            print(f"Writing results to {result_filename}")
            with open(result_filename, "w") as f:
                f.write(html)


if __name__ == "__main__":
    main()
