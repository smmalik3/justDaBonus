#!/usr/bin/env python

import argparse
from flask import *
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

@app.route('/')
def index():
  scope = ['https://spreadsheets.google.com/feeds']
  credentials = ServiceAccountCredentials.from_json_keyfile_name('test-3f652713c268.json', scope)

  gc = gspread.authorize(credentials)

  spreadsheet = gc.open("test")
  wks = spreadsheet.sheet1
  emp_names = wks.col_values(1)
  return render_template('index.html', title="Bonus", emp_names=emp_names)

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Its a POC so dont expect anything, ok?")
  parser.add_argument("--debug", help="Debugger mode", required=False, action="store_true", default=False)
  parser.add_argument("--port", help="Pert number", type=int, required=False, default=8888)
  args = parser.parse_args()

  app.run(host="0.0.0.0", port=args.port, debug=args.debug)
