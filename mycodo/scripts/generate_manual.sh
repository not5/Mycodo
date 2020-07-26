#!/bin/bash
# Generates the Mycodo Manual in different formats with pandoc
#
# Dependencies
#
# Debian/Ubuntu
# sudo apt-get install pandoc texlive texlive-latex-extra
#
# Fedora
# sudo yum install pandoc texlive texlive-collection-latexextra

INSTALL_DIRECTORY=$( cd "$( dirname "${BASH_SOURCE[0]}" )/../../" && pwd -P )
cd "${INSTALL_DIRECTORY}" || return

# check if pandoc is installed
if [[ $(command -v pandoc) ]]
then
  # Reformat restructuredtext
  pandoc -s --toc --toc-depth=4 -f rst -t rst -o "${INSTALL_DIRECTORY}"/mycodo-manual.rst "${INSTALL_DIRECTORY}"/mycodo-manual.rst

  # Delete line after ".. raw:: html"
  sed -i '/^.. raw:: html/{n;d}' "${INSTALL_DIRECTORY}"/mycodo-manual.rst
  # Delete line after "   <div class="contents">"
  sed -i '/^   <div class="contents">/{n;d}' "${INSTALL_DIRECTORY}"/mycodo-manual.rst
  # Delete line after "   </div>"
  sed -i '/^   <\/div>/{n;d}' "${INSTALL_DIRECTORY}"/mycodo-manual.rst

  # Delete line ".. raw:: html"
  sed -i '/^.. raw:: html/d' "${INSTALL_DIRECTORY}"/mycodo-manual.rst
  # Delete line "   <div class="contents">"
  sed -i '/^   <div class="contents">/d' "${INSTALL_DIRECTORY}"/mycodo-manual.rst
  # Delete line "   </div>"
  sed -i '/^   <\/div>/d' "${INSTALL_DIRECTORY}"/mycodo-manual.rst

  # Generate PDF file
  pandoc -V geometry:margin=0.5in --table-of-contents -s -o "${INSTALL_DIRECTORY}"/docs/mycodo-manual.pdf "${INSTALL_DIRECTORY}"/mycodo-manual.rst

  # Generate HTML (HTML5) file
  pandoc --table-of-contents -H "${INSTALL_DIRECTORY}"/mycodo/scripts/pandoc.css_style --self-contained -s -t html5 -o "${INSTALL_DIRECTORY}"/docs/mycodo-manual.html "${INSTALL_DIRECTORY}"/mycodo-manual.rst
  cp "${INSTALL_DIRECTORY}"/docs/mycodo-manual.html "${INSTALL_DIRECTORY}"/mycodo/mycodo_flask/static/manual/mycodo-manual.html

  # Generate plain text
  pandoc --table-of-contents -s -t plain -o "${INSTALL_DIRECTORY}"/docs/mycodo-manual.txt "${INSTALL_DIRECTORY}"/mycodo-manual.rst
else
  printf "The command pandoc could not be found in the PATH!"
fi
