PAPER := main

.PHONY: all watch clean help

all:
	latexmk -pdf -synctex=1 -interaction=nonstopmode -file-line-error $(PAPER).tex

watch:
	latexmk -pdf -synctex=1 -pvc -interaction=nonstopmode -file-line-error $(PAPER).tex

clean:
	latexmk -C
	rm -f *.bbl *.synctex.gz *.run.xml *.bcf

help:
	@echo "make         build the paper once"
	@echo "make watch   continuous build on save (uses latexmk -pvc)"
	@echo "make clean   remove all build artifacts"
