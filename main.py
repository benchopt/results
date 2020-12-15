import shutil
from pathlib import Path
from datetime import datetime
import glob

import click
from mako.template import Template
from pygments.formatters import HtmlFormatter
import matplotlib
import matplotlib.pyplot as plt

import pandas as pd
from benchopt.viz import PLOT_KINDS

matplotlib.use('Agg')

ROOT = Path(__file__).parent
BUILD_DIR = Path(__file__).parent / "build"
BUILD_DIR_OUTPUTS = BUILD_DIR / "outputs"
BUILD_DIR_FIGURES = BUILD_DIR / "figures"

TEMPLATE_INDEX = ROOT / "templates" / "index.mako.html"
TEMPLATE_BENCHMARK = ROOT / "templates" / "benchmark.mako.html"
TEMPLATE_RESULT = ROOT / "templates" / "result.mako.html"

JQUERY_JS = ROOT / "resources" / "jquery.js"
JQUERY_DATATABLES_JS = ROOT / "resources" / "jquery.dataTables.min.js"
JQUERY_DATATABLES_CSS = ROOT / "resources" / "jquery.dataTables.min.css"
JQUERY_DATATABLES_JS = ROOT / "resources" / "jquery.dataTables.min.js"
JQUERY_DATATABLES_CSS = ROOT / "resources" / "jquery.dataTables.min.css"


def plot_benchmark(df, kinds=PLOT_KINDS):
    """Plot convergence curve and histogram for a given benchmark.

    Parameters
    ----------
    df : instance of pandas.DataFrame
        The benchmark results.
    kinds : list of str or None
        List of the plots that will be generated. If None are provided, use the
        config file to choose or default to suboptimality_curve.

    Returns
    -------
    figs : list
        The matplotlib figures for convergence curve and histogram
        for each dataset.
    """
    datasets = df['data_name'].unique()
    figs = []
    for data in datasets:
        df_data = df[df['data_name'] == data]
        objective_names = df['objective_name'].unique()
        for objective_name in objective_names:
            df_obj = df_data[df_data['objective_name'] == objective_name]

            for k in kinds:
                if k not in PLOT_KINDS:
                    raise ValueError(
                        f"Requesting invalid plot '{k}'. Should be in:\n"
                        f"{PLOT_KINDS}")
                plt.figure()
                fig = PLOT_KINDS[k](df_obj)
                figs.append(fig)

    return figs


def get_results(fnames):
    results = []
    BUILD_DIR_OUTPUTS.mkdir(exist_ok=True, parents=True)
    BUILD_DIR_FIGURES.mkdir(exist_ok=True, parents=True)

    for fname in fnames:
        print(f"Processing {fname}")
        fname_path = Path(fname)
        df = pd.read_csv(fname)
        fname_no_output = fname.replace('outputs/', '')
        fname_no_output_path = Path(fname_no_output)

        # Copy CSV
        shutil.copy(fname, BUILD_DIR_OUTPUTS / fname_no_output_path)

        result = dict(
            fname_short=fname.replace('outputs/', '').replace('/', '_'),
            fname=fname,
            fig_fnames=[]
        )

        # Produce figures
        figs = plot_benchmark(df)

        for k, fig in enumerate(figs):
            fig_basename = f"{result['fname_short']}_{k}.svg"
            save_name = BUILD_DIR_FIGURES / fig_basename
            fig.savefig(save_name)
            result['fig_fnames'].append(f'figures/{fig_basename}')
            plt.close(fig)

        results.append(result)

    for result in results:
        result['page'] = \
            f"{result['fname_short'].replace('.csv', '.html')}"

    return results


def render_benchmark(results, benchmark):
    cssclass = "highlight"
    formatter = HtmlFormatter(cssclass=cssclass)

    table_formatter_css = JQUERY_DATATABLES_CSS.read_text("utf-8")
    table_formatter_js = (
        JQUERY_JS.read_text("utf-8")
        + "\n"
        + JQUERY_DATATABLES_JS.read_text("utf-8")
    )
    return Template(filename=str(TEMPLATE_BENCHMARK),
                    input_encoding="utf-8").render(
        results=results,
        benchmark=benchmark,
        code_formatter_css=formatter.get_style_defs(f'.{cssclass}'),
        table_formatter_css=table_formatter_css,
        table_formatter_js=table_formatter_js,
        max_rows=15,
        nb_total_benchs=len(results),
        last_updated=datetime.now(),
    )


def render_index(benchmarks):
    cssclass = "highlight"
    formatter = HtmlFormatter(cssclass=cssclass)

    table_formatter_css = JQUERY_DATATABLES_CSS.read_text("utf-8")
    table_formatter_js = (
        JQUERY_JS.read_text("utf-8")
        + "\n"
        + JQUERY_DATATABLES_JS.read_text("utf-8")
    )
    return Template(filename=str(TEMPLATE_INDEX),
                    input_encoding="utf-8").render(
        benchmarks=benchmarks,
        code_formatter_css=formatter.get_style_defs(f'.{cssclass}'),
        table_formatter_css=table_formatter_css,
        table_formatter_js=table_formatter_js,
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
    cssclass = "highlight"
    formatter = HtmlFormatter(cssclass=cssclass)

    htmls = []
    for result in results:
        html = Template(
            filename=str(TEMPLATE_RESULT),
            input_encoding="utf-8").render(
            result=result,
            benchmark=benchmark,
            code_formatter_css=formatter.get_style_defs(f'.{cssclass}'),
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
