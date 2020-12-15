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
OUTPUT_DIR = Path(__file__).parent / "rendered"
OUTPUT_BENCH_DIR = OUTPUT_DIR / "outputs"
OUTPUT_FIG_DIR = OUTPUT_DIR / "figures"
TEMPLATE = ROOT / "templates" / "index.mako.html"
TEMPLATE_RESULT = ROOT / "templates" / "result.mako.html"
JQUERY_DATATABLES_JS = ROOT / "resources" / "jquery.dataTables.min.js"
JQUERY_DATATABLES_CSS = ROOT / "resources" / "jquery.dataTables.min.css"
JQUERY_JS = ROOT / "resources" / "jquery.js"
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
    OUTPUT_BENCH_DIR.mkdir(exist_ok=True, parents=True)
    OUTPUT_FIG_DIR.mkdir(exist_ok=True, parents=True)

    for fname in fnames:
        print(f"Processing {fname}")
        fname_path = Path(fname)
        df = pd.read_csv(fname)

        # Copy CSV
        shutil.copy(fname, OUTPUT_BENCH_DIR / fname_path.name)

        result = dict(
            fname_short=fname.replace('outputs/', ''),
            fname=fname,
            fig_fnames=[]
        )

        # Produce figures
        figs = plot_benchmark(df)

        for k, fig in enumerate(figs):
            fig_basename = f"{result['fname_short']}_{k}.svg"
            save_name = OUTPUT_FIG_DIR / fig_basename
            fig.savefig(save_name)
            result['fig_fnames'].append(f'figures/{fig_basename}')
            plt.close(fig)

        results.append(result)

    for result in results:
        result['page'] = \
            f"{result['fname_short'].replace('.csv', '.html')}"

    return results


def render_index(results):
    cssclass = "highlight"
    formatter = HtmlFormatter(cssclass=cssclass)

    table_formatter_css = JQUERY_DATATABLES_CSS.read_text("utf-8")
    table_formatter_js = (
        JQUERY_JS.read_text("utf-8")
        + "\n"
        + JQUERY_DATATABLES_JS.read_text("utf-8")
    )
    return Template(filename=str(TEMPLATE), input_encoding="utf-8").render(
        results=results,
        code_formatter_css=formatter.get_style_defs(f'.{cssclass}'),
        table_formatter_css=table_formatter_css,
        table_formatter_js=table_formatter_js,
        max_rows=15,
        nb_total_benchs=len(results),
        last_updated=datetime.now(),
    )


def copy_static():
    dst = OUTPUT_DIR / 'static'
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / 'static', dst)


def render_all_results(results):
    cssclass = "highlight"
    formatter = HtmlFormatter(cssclass=cssclass)

    htmls = []
    for result in results:
        html = Template(
            filename=str(TEMPLATE_RESULT),
            input_encoding="utf-8").render(
            result=result,
            code_formatter_css=formatter.get_style_defs(f'.{cssclass}'),
        )
        htmls.append(html)
    return htmls


@click.command()
@click.option('--pattern', '-k', 'patterns',
              metavar="<pattern>", multiple=True, type=str,
              help="Include results matching <pattern>.")
def main(patterns=None):
    if not patterns:
        patterns = ['*']
    fnames = []
    for p in patterns:
        fnames += glob.glob(f'outputs/{p}.csv')
    fnames = sorted(set(fnames))
    results = get_results(fnames)
    rendered = render_index(results)
    copy_static()

    index_filename = OUTPUT_DIR / "index.html"
    print(f"Writing results to {index_filename}")
    with open(index_filename, "w") as f:
        f.write(rendered)

    htmls = render_all_results(results)
    for result, html in zip(results, htmls):
        result_filename = OUTPUT_DIR / result['page']
        print(f"Writing results to {result_filename}")
        with open(result_filename, "w") as f:
            f.write(html)


if __name__ == "__main__":
    main()
