from flask import Flask, request, jsonify, render_template, send_file, url_for
from flask_table import Table, Col
from requests.auth import HTTPBasicAuth
from configparser import ConfigParser
from pprint import pprint

import smtplib

import truffleHog
import json
import glob
import requests
import urllib.parse
#import sys
from subprocess import Popen, PIPE
import re
import csv
import os.path
from datetime import datetime
from asyncore import read
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

#
# Global variables
#
app = Flask(__name__)

settings = {}

# Naming convention
report_name_prefix = "secrets_report"
config_file = "config.ini"

# all_secrets as a global may be obsolete...
all_secrets = {}

# End Global variables

# Declare your table
class ItemTable(Table):
    classes = ["table", "results"]
    url = Col('URL')
    branch = Col('Branch')
    commit = Col('Commit')
    commit_hash = Col('Commit Hash')
    date = Col('Date')
    path = Col('Path')
    print_diff = Col('Print Diff')
    reason = Col('Reason')
    strings_found = Col('Strings Found')
    

# Get some objects
class Item(object):
    def __init__(self, url, branch, commit, commit_hash, date, path, print_diff, reason, strings_found):
        self.url = url
        self.branch = branch
        self.commit = commit
        self.commit_hash = commit_hash
        self.date = date
        self.path = path
        self.print_diff = print_diff
        self.reason = reason
        self.strings_found = strings_found

def remove_ansi(line):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', line)

def to_table(findings):
    items = []
    for key in findings:
        value = findings[key]
        json_values = json.loads(value)
        for json_value in json_values:
            items.append(Item(key, json_value['branch'], json_value['commit'], json_value['commitHash'], json_value['date'], json_value['path'], json_value['printDiff'], json_value['reason'], json_value['stringsFound']))

    table = ItemTable(items)
    return table.__html__() 

def to_list(urls):
    html = '<ul>'
    for url in urls :
        html += '<li>' + url + '</li>'
    html += '</ul>'
    return html
def fix_json(data):
    data = "[" + data.replace("]}", "]},", data.count("]}")-1) + "]"
    return data

# Adding JSON functionality, to replace old data structure
def to_file(report_name, findings, html):
                                                    
    with open(settings['report_dir'] + '/' + report_name, 'w') as csvfile:
        writer = csv.writer(csvfile,dialect='excel',quoting=csv.QUOTE_ALL)
        writer.writerow(["URL", "Branch", "Commit", "Commit Hash", "Date", "Path", "Print Diff", "Reason", "Strings Found"])
        for key in findings:
            value = findings[key]
            json_values = json.loads(value)
            for json_value in json_values:
                writer.writerow([key,json_value['branch'],json_value['commit'],json_value['commitHash'],json_value['date'],json_value['path'],json_value['printDiff'],json_value['reason'],''.join(json_value['stringsFound'])])
        csvfile.flush()
        csvfile.close()

    report_name_json = report_name.replace(".csv", ".json")
    fdrnj = settings['report_dir'] + '/' + report_name_json
    with open(fdrnj, 'w') as jf:
        json.dump(html, jf)
    '''
    report_name_html = report_name.replace(".csv", ".html")
                                           
    htmlfile = open(settings['report_dir'] + report_name_html, "w")
    htmlfile.write(html)
    htmlfile.close()
    '''
        

def get_github_urls(userid, password,orgs, users):
    urls = []
    if orgs.strip():
        for org in orgs.split('\n'):
            print(org);
            response = requests.get('https://api.github.com/orgs/' + org.strip() + '/repos', auth=HTTPBasicAuth(userid, password))
            print(response.json())
            for repo in response.json():
                urls.append(repo['clone_url'])
    if users.strip():
        for user in users.split('\n'):
            print(user)
            response = requests.get('https://api.github.com/users/' + user.strip() + '/repos', auth=HTTPBasicAuth(userid, password))
            print(response.json())
            for repo in response.json():
                urls.append(repo['clone_url'])
    print(urls)
    return urls

def get_bitbucket_urls(userid, password,base_url):
    print("scanning bitbucket")
    urls = []
    is_last_page = False
    next_page_start = '0'

    while not is_last_page:
        response = requests.get(base_url + '/rest/api/1.0/repos?limit=' + str(settings['page_size']) + '&start=' + str(next_page_start), auth=HTTPBasicAuth(userid, password))
        print(response.json())
        response_json = response.json()
        is_last_page = response_json['isLastPage']
        if 'nextPageStart' in response_json:
            next_page_start = response_json['nextPageStart']
        for repo in response_json['values']:
            links = repo['links']['clone']
            for link in links:
                print(link)
                if link['name'] == 'http':
                    urls.append(link['href'])
    print(urls)
    return urls

def get_gitlab_urls(token, base_url):
    print("scanning gitlab")
    headers = {"PRIVATE-TOKEN": token}

    urls = []
    is_last_page = False
    next_page_start = '1'

    while not is_last_page:
        response = requests.get(base_url + '/api/v4/projects?simple=true&per_page=' + str(settings['page_size']) + '&page=' + str(next_page_start), headers=headers)
        print(response.json())
        response_json = response.json()
        response_headers = response.headers
        print(response_headers)
        is_last_page = response_headers['X-Next-Page'] == '' 
        next_page_start = response_headers['X-Next-Page']
        for project in response_json:
            urls.append(project['http_url_to_repo'])
    print(urls)
    return urls
    
def get_azure_devops_urls(userid, password, org):
    urls = []

    response = requests.get('https://dev.azure.com/' + org.strip() + '/_apis/git/repositories?api-version=6.0&includeAllUrls=true', auth=HTTPBasicAuth(userid, password))
    print(response.json())
    for repo in response.json()['value']:
        urls.append(repo['webUrl'])
    pprint(urls)   
    return urls 
    
def repo_to_file_name(repo):
    file_name = repo.strip()
    file_name = file_name.replace("https://", "")
    file_name = file_name.replace("http://", "")
    file_name = file_name.replace("/", "~")
    file_name = file_name.replace("/", "~")
    file_name = file_name.replace("\n", "")
    file_name = file_name.replace("\r", "")
    return file_name

def file_exists(file_name):
    exists = os.path.isfile(file_name)
    return exists

def read_config():
    if not file_exists(config_file):
        write_config("/tmp","100","", "", "", "", "")
    
    
    config = ConfigParser()
    global settings 
    settings = {}
    config.read(config_file)
    
    settings['report_dir'] = config.get('general', 'report_dir')
    settings['page_size'] = config.get('general', 'page_size')
    settings['server'] = config.get('smtp', 'server')
    settings['port'] = config.get('smtp', 'port')
    settings['from_address'] = config.get('smtp', 'from_address')
    settings['userid'] = config.get('smtp', 'userid')
    settings['password'] = config.get('smtp', 'password')
    
    print(settings)
    return settings

def write_config(report_dir, page_size, server, port, from_address, userid, password):
    config = ConfigParser()

    config.add_section('general')
    config.set('general', 'report_dir', report_dir)
    config.set('general', 'page_size', page_size)

    config.add_section('smtp')
    config.set('smtp', 'server', server)
    config.set('smtp', 'port', port)
    config.set('smtp', 'from_address', from_address)
    config.set('smtp', 'userid', userid)
    config.set('smtp', 'password', password)
    with open('config.ini', 'w') as f:
        config.write(f)
    #update the global settings variable
    read_config()
    
    return

def email_report(report_recipients, report_name):
    settings = read_config()
    
    msg = MIMEMultipart()
    body_part = MIMEText("Attached is the results of the Secret Scan.", 'plain')
    msg['Subject'] = "Secret Scanner Results"
    msg['From'] = settings['from_address']
    msg['To'] = report_recipients
    # Add body to email
    msg.attach(body_part)
    # open and read the CSV file in binary
    with open(settings['report_dir'] + '/' + report_name,'rb') as file:
    # Attach the file with filename to the email
        msg.attach(MIMEApplication(file.read(), Name=report_name))

    # Create SMTP object
    smtp_obj = smtplib.SMTP(settings['server'], settings['port'])
    # Login to the server
    if settings['userid'] and settings['password']:
        smtp_obj.login(settings['userid'], settings['password'])

    # Convert the message to a string and send it
    smtp_obj.sendmail(msg['From'], msg['To'], msg.as_string())
    smtp_obj.quit()
@app.route('/')
def home():
    read_config()
    return render_template('index.html', email_server = settings['server'], email_server_port = settings['port'], email_from = settings['from_address'], email_userid = settings['userid'], email_password = settings['password'], report_dir = settings['report_dir'], page_size = settings['page_size'])

@app.route('/config',methods=['POST'])
def config():
    form = request.form
    server = form['email_server']
    port = form['email_server_port']
    from_address = form['email_from']
    userid = form['email_userid']
    password = form['email_password']
    report_dir = form['report_directory']
    page_size = form['page_size']
    write_config(report_dir, page_size, server, port, from_address, userid, password)
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

@app.route('/scan',methods=['POST'])
def scan():
    settings = read_config()

    form = request.form
    userid = form['userid']
    password = form['password']
    repo_scan_type = form['gitgroup']
    entropy = False
    report_recipients = form['report_recipients']
    
    if form.get('entropy'):
        entropy = True
        
    rescan = False
    if form.get('rescan'):
        rescan = True
        
    urls = []

    print("repo_scan_type:" + repo_scan_type)

    if repo_scan_type  == 'github':
        urls = get_github_urls(userid, password, form['github_orgs'], form['github_users'])
    elif repo_scan_type  == 'bitbucket':
        urls = get_bitbucket_urls(userid, password, form['url'])
    elif repo_scan_type  == 'gitlab':
        urls = get_gitlab_urls(password, form['url'])
    elif repo_scan_type  == 'azure':
        urls = get_azure_devops_urls(userid, password, form['azure_organization'])
    elif repo_scan_type == 'generic':
        urls = form['git_urls']

    all_secrets = {}
    found_secrets = {}
    
    scanned=[]
    skipped=[]
    
    key_id = 0
    
    pprint(settings)
    
    for repo in urls:
        if repo.strip():
            repo_pass = repo
            if userid and password:
                repo_pass = repo.replace("://", "://" + urllib.parse.quote_plus(userid) + ":" + urllib.parse.quote_plus(password) + "@")
            file_name = settings['report_dir'] + '/' + repo_to_file_name(repo)
            # skip repos we've previously scanned with rescan is not checked
            if not rescan:
                if file_exists(file_name):
                    print('skipping scan of ' + file_name)
                    skipped.append(repo)
                    continue
                
            '''
            # Comment this out for faster running for developmental purpose
            file = open(file_name, "w")
            cmd = "trufflehog --json --regex --entropy=" + str(entropy) + " " + repo_pass 
            p1=Popen(cmd,shell=True,stdout=file)
            p1.wait()
            file.flush()
            file.close()
            # Comment up to here
            '''

            file = open(file_name, "r")
            
            # New Changes
            allout = file.readlines()
            found_secrets[repo] = []
            
            for ln in allout:
                jl = json.loads(ln.strip())
                jl["key_id"] = key_id
                key_id += 1
                found_secrets[repo].append(jl.copy())

            file.close()

            # Below may be obsolete
            all_secrets[repo] = []
            file = open(file_name, "r")
            output = file.read()
            file.close()

            scanned.append(repo)

            all_secrets[repo] = fix_json(remove_ansi(output))


    now = datetime.now()
    report_name = report_name_prefix + now.strftime("_%Y_%m_%d_%H%M%S") + ".csv"

    '''
    table_html = to_table(all_secrets)
    scanned_urls_html = to_list(scanned)
    skipped_urls_html = to_list(skipped)
    '''
    # Adding json functionality
    # to_file(report_name, all_secrets, table_html)
    to_file(report_name, all_secrets, found_secrets)

    if report_recipients:
        email_report(report_recipients, report_name)

    #return render_template('results.html', scan_results=f'{table_html}', scanned_urls=f'{scanned_urls_html}',  skipped_urls=f'{skipped_urls_html}', report_name=f'{report_name}')
    return render_template('results.html', scan_results=found_secrets, scanned_urls=scanned,  skipped_urls=skipped, report_name=f'{report_name}')

@app.route('/previous_results',methods=['GET', 'POST'])
def previous_results():
    previous_results = sorted(glob.glob(settings['report_dir'] + '/' + report_name_prefix + '*'),reverse=True)
    links = {}
    for result in previous_results:
        # TODO! This might need to be changed to "\\" on WINDOWS computers
        sr_name = result.split(".")[0].split("/")[-1]
        sr_ext = result.split(".")[1]
        if sr_name not in links:
            links[sr_name] = {}
        # TODO! This might need to be changed to "\\" on WINDOWS computers
        resd = result.rsplit('/',1)[-1]
        links[sr_name][sr_ext] = request.url_root + url_for('download', file=resd)[1:]
    return render_template('previous_results.html', results_list=links)

@app.route('/download/<file>',methods=['GET','POST'])
def download (file):
    settings = read_config()
    path = settings['report_dir'] + '/' + file
    # TODO if file.startswith(report_name_prefix):
    if file.endswith('.csv'):
        if not file.startswith(report_name_prefix):
            path = file
        return send_file(path, as_attachment=True)
    elif file.endswith('.json'):
        if not file.startswith(report_name_prefix):
            path = file
        thefile = open(path, "r")
        found_secrets = json.load(thefile)

        # Find the csv file based on json file name
        to_csv = file[:-4] + "csv"
            
        return render_template('previous_result.html', scan_results=found_secrets, report_name=to_csv)

    return "Not Allowed"

if __name__ == "__main__":
    app.run(port=5000)
    app.config["TEMPLATES_AUTO_RELOAD"] = True