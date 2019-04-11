# justDaBonus

This is a Python Flask app built for giving bonuses to coworkers at Signal.

The data gets piped back and forth from a google spreadsheet.


To run app locally in a virtualenv:
1. Activate virtualenv
2. cd /mnt/src/pypr
3. Run following command:
   ./pants binary justdabonus && rm -rf dist/explode && mkdir dist/explode && cd dist/explode && unzip ../justdabonus.pex && python ../explode --debug
