PYTHON?=python

BASEDIR=$(CURDIR)
OUTPUTDIR=$(BASEDIR)/rendered

GITHUB_PAGES_BRANCH=gh-pages

render:
	${PYTHON} main.py

publish: render
	touch $(OUTPUTDIR)/.nojekyll
	ghp-import -m "Generate site" -b $(GITHUB_PAGES_BRANCH) $(OUTPUTDIR)
	git push origin $(GITHUB_PAGES_BRANCH)

