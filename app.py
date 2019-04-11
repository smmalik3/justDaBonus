#!/usr/bin/env python

from gevent.monkey import patch_all; patch_all()
import os
import argparse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
from flask import Flask, jsonify, render_template, request, make_response, session, redirect
import authomatic
from authomatic.adapters import WerkzeugAdapter
from authomatic import Authomatic
from authomatic.providers import oauth2
from gevent.wsgi import WSGIServer
from co.signal.http.management.healthcheck import healthcheck

def setup_routes(app, debug, spreadsheet_name):
  OAUTH_CONFIG = {
    "google": {
      "class_": oauth2.Google,
      "id": authomatic.provider_id(),
      "consumer_key": "678365835388-gt8b1d2voof0n6cffe5ljdgu80qaand4.apps.googleusercontent.com",
      "consumer_secret": "kK2vuS9muxml3cISlb5w5bRp",
      "scope": ["profile", "email"]
    }
  }
  authomatic_config = Authomatic(OAUTH_CONFIG, "asda", report_errors=False)
  valid_domain = "@signal.co"

  if not debug:
    # if we're on production make sure we're always on https
    @app.before_request
    def before_request():
      if not request.headers.get('X-Forwarded-Proto', '').startswith('https'):
        return redirect(request.url.replace('http://', 'https://', 1), code=301)

  @app.route("/login/<provider_name>/", methods=["GET", "POST"])
  def login(provider_name):
    response = make_response()
    result = authomatic_config.login(
      WerkzeugAdapter(request, response),
      provider_name,
      session=session,
      session_saver=lambda: app.save_session(session, response)
    )
    if result:
      if result.user:
        result.user.update()
        if valid_domain not in result.user.email:
          return render_template("index.html", message="Please login with a valid @signal.co email address.")
        session["email"] = result.user.email
        session["name"] = result.user.name
        return redirect("/")
      return logout_error()
    return response

  @app.route("/", methods=["GET"])
  def index():
    email, name = session.get("email", None), session.get("name", None)
    return render_template("index.html", email=email, name=name)

  def open_spreadsheet(names=False):
    scope = ["https://spreadsheets.google.com/feeds"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(os.path.join(os.path.dirname(__file__), "test-3f652713c268.json"), scope)
    gc = gspread.authorize(credentials)
    spreadsheet = gc.open(spreadsheet_name)
    return spreadsheet.get_worksheet(1 if names else 0)

  def get_employees():
    name_worksheet = open_spreadsheet(True)
    employee_names, region_codes, employee_ids = name_worksheet.col_values(1), name_worksheet.col_values(2), name_worksheet.col_values(3)
    return [{"name": name, "region": region_codes[i], "id": employee_ids[i]} for i, name in enumerate(employee_names)]

  @app.route("/employees.json")
  def employees():
    if session:
      employees = get_employees()
      return jsonify(data=[employee["name"] for employee in employees if employee["name"]])
    return 'Um, nah brah', 403

  @app.route("/", methods=["POST"])
  def handle_submit():
    bonus_worksheet, name_worksheet = open_spreadsheet(False), open_spreadsheet(True)
    month, year = time.strftime("%b %y").split(' ')
    email, name = session.get("email", None), session.get("name", None)
    month_name = month + name
    validation_result = validate_form(month_name, request.form, session, bonus_worksheet, name_worksheet)
    if validation_result:
      return render_template("index.html", message=validation_result, email=email, name=name)
    else:
      give_bonus(month, year, request.form, name, bonus_worksheet)
      return render_template("index.html", confirmation="Your bonus is on its way!", email=email, name=name)

  def give_bonus(month, year, bonus_request, sender_name, bonus_worksheet):
    recipient_name, comments, informed_status = bonus_request["recipient"], bonus_request["comments"], bonus_request["informed_status"]
    month_year_name = month + year + sender_name
    employees = get_employees()
    person = next(employee for employee in employees if employee["name"] == recipient_name)
    recipient, employee_id, region_code = person["name"], person["id"], person["region"]
    last_row_num = 0
    for row_num, value in enumerate(bonus_worksheet.col_values(1)):
      if not value:
        last_row_num = row_num
        break
    last_row_num += 1
    bonus_worksheet.update_acell("A{}".format(last_row_num), month + year)
    bonus_worksheet.update_acell("B{}".format(last_row_num), recipient)
    bonus_worksheet.update_acell("C{}".format(last_row_num), region_code)
    bonus_worksheet.update_acell("D{}".format(last_row_num), comments)
    bonus_worksheet.update_acell("E{}".format(last_row_num), informed_status)
    bonus_worksheet.update_acell("F{}".format(last_row_num), sender_name)
    bonus_worksheet.update_acell("G{}".format(last_row_num), month_year_name)
    bonus_worksheet.update_acell("H{}".format(last_row_num), employee_id)

  def validate_form(month_name, form, session, bonus_worksheet, name_worksheet):
    recipient = form["recipient"]
    if self_bonus(form, session):
      return "You can't bonus yourself!"
    if validate_redundancy(month_name, bonus_worksheet):
      return "You've already submitted a bonus for this month!"
    if not validate_input(form, name_worksheet):
      return "Please fill out all the fields correctly."

  def self_bonus(form, session):
    recipient = form["recipient"]
    name = session.get("name", None)
    return recipient == name

  def validate_redundancy(month_name, bonus_worksheet):
    already_bonused = bonus_worksheet.findall(month_name)
    return True if already_bonused else False

  def validate_input(form, name_worksheet):
    recipient = form["recipient"]
    comment = form["comments"]
    informed_status = form.get("informed_status", None)
    emp_names = [e for e in name_worksheet.col_values(1) if e]
    if recipient not in emp_names:
      return False
    if len(comment.strip()) == 0: #check length and trim
      return False
    return False if not informed_status else True

  def logout_error():
    session.clear()
    return render_template("index.html", message="Something went wrong, please try logging in again.")

  @app.route('/logout')
  def logout():
    session.clear()
    return render_template("index.html", message="k, BAI.")

def main(argv=None):
  parser = argparse.ArgumentParser(description="This is a program to give monthly bonuses between Signal Employees")
  parser.add_argument("--debug", help="Debugger mode", required=False, action="store_true", default=False)
  parser.add_argument("--port", help="Pert number", type=int, required=False, default=8888)
  parser.add_argument("--spreadsheet-name", help="Spreadsheet Name", type=str, default='BT Bonus Spreadsheet')
  parser.add_argument("--config", help="Config File", type=str, default='')
  args = parser.parse_args()

  spreadsheet_name = args.spreadsheet_name
  app = Flask(__name__)
  app.secret_key = "som3th1ngg00f"
  app.register_blueprint(healthcheck)

  setup_routes(app, debug=args.debug, spreadsheet_name=spreadsheet_name)

  if args.debug:
    app.run(host='0.0.0.0', port=args.port, debug=True)
  else:
    http_server = WSGIServer(('', args.port), app, log=None)
    http_server.serve_forever()

if __name__ == "__main__":
  main()