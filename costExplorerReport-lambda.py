#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Cost Explorer Report

A script, for local or lambda use, to generate CostExplorer excel graphs

"""

from __future__ import print_function

__author__ = "David Faulkner"
__version__ = "0.1.1"
__license__ = "MIT No Attribution"

import os
import sys
# Required to load modules from vendored subfolder (for clean development env)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "./vendored"))

import boto3
import datetime
import logging
import pandas as pd
#For date
from dateutil.relativedelta import relativedelta
#For email
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

#GLOBALS
SES_REGION = os.environ.get('SES_REGION')
if not SES_REGION:
    SES_REGION="us-east-1"
ACCOUNT_LABEL = os.environ.get('ACCOUNT_LABEL')
if not ACCOUNT_LABEL:
    ACCOUNT_LABEL = 'Email'

CURRENT_MONTH = os.environ.get('CURRENT_MONTH')
if CURRENT_MONTH == "true":
    CURRENT_MONTH = True
else:
    CURRENT_MONTH = False

class CostExplorer:
    """Retrieves BillingInfo checks from CostExplorer API
    >>> costexplorer = CostExplorer()
    >>> costexplorer.addReport(GroupBy=[{"Type": "DIMENSION","Key": "SERVICE"}])
    >>> costexplorer.generateExcel()
    """
    def __init__(self, ACCESS_KEY=None, SECRET_KEY=None, SESSION_TOKEN=None, CurrentMonth=False):
        #Array of reports ready to be output to Excel.
        self.reports = []
        self.client = boto3.client('ce', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY, aws_session_token=SESSION_TOKEN, region_name='us-east-1')
        self.end = datetime.date.today().replace(day=1)# - datetime.timedelta(days=1) # last day of last month
        self.riend = datetime.date.today()
        if CurrentMonth or CURRENT_MONTH:
            self.end = self.riend
        self.start = (datetime.date.today() - relativedelta(months=+12)).replace(day=1) #1st day of month 11 months ago
        self.ristart = (datetime.date.today() - relativedelta(months=+11)).replace(day=1) #1st day of month 11 months ago
        try:
            self.accounts = self.getAccounts()
        except:
            logging.exception("Getting Account names failed")
            self.accounts = {}

    def getAccounts(self, ACCESS_KEY=None, SECRET_KEY=None, SESSION_TOKEN=None):
        accounts = {}
        client = boto3.client('organizations', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY, aws_session_token=SESSION_TOKEN, region_name='us-east-1')
        paginator = client.get_paginator('list_accounts')
        response_iterator = paginator.paginate()
        for response in response_iterator:
            for acc in response['Accounts']:
                accounts[acc['Id']] = acc
        return accounts

    def addRiReport(self, Name="RICoverage"):
        results = []
        response = self.client.get_reservation_coverage(
            TimePeriod={
                'Start': self.ristart.isoformat(),
                'End': self.riend.isoformat()
            },
            Granularity='MONTHLY'
        )
        results.extend(response['CoveragesByTime'])
        while 'nextToken' in response:
            nextToken = response['nextToken']
            response = self.client.get_reservation_coverage(
                TimePeriod={
                    'Start': self.ristart.isoformat(),
                    'End': self.riend.isoformat()
                },
                Granularity='MONTHLY',
                NextPageToken=nextToken
            )
            results.extend(response['CoveragesByTime'])
            if 'nextToken' in response:
                nextToken = response['nextToken']
            else:
                nextToken = False

        rows = []
        for v in response['CoveragesByTime']:
            row = {'date':v['TimePeriod']['Start']}
            row.update({'Coverage%':float(v['Total']['CoverageHours']['CoverageHoursPercentage'])})
            rows.append(row)

        df = pd.DataFrame(rows)#index=[i['date'] for i in rows]
        df.set_index("date", inplace= True)
        df = df.fillna(0.0)
        df = df.T
        self.reports.append({'Name':Name,'Data':df})


    def addReport(self, Name="Default",GroupBy=[{"Type": "DIMENSION","Key": "SERVICE"},],
    Style='Total', NoCredits=True, CreditsOnly=False, UpfrontOnly=False):
        results = []
        if not NoCredits:
            response = self.client.get_cost_and_usage(
                TimePeriod={
                    'Start': self.start.isoformat(),
                    'End': self.end.isoformat()
                },
                Granularity='MONTHLY',
                Metrics=[
                    'UnblendedCost',
                ],
                GroupBy=GroupBy
            )
        else:
            Filter={"Not": {"Dimensions": {"Key": "RECORD_TYPE","Values": ["Credit", "Refund", "Upfront"]}}}
            if CreditsOnly:
                Filter={"Dimensions": {"Key": "RECORD_TYPE","Values": ["Credit", "Refund"]}}
            if UpfrontOnly:
                Filter={"Dimensions": {"Key": "RECORD_TYPE","Values": ["Upfront",]}}
            response = self.client.get_cost_and_usage(
                TimePeriod={
                    'Start': self.start.isoformat(),
                    'End': self.end.isoformat()
                },
                Granularity='MONTHLY',
                Metrics=[
                    'UnblendedCost',
                ],
                GroupBy=GroupBy,
                Filter=Filter
            )

        if response:
            results.extend(response['ResultsByTime'])

            while 'nextToken' in response:
                nextToken = response['nextToken']
                response = self.client.get_cost_and_usage(
                    TimePeriod={
                        'Start': self.start.isoformat(),
                        'End': self.end.isoformat()
                    },
                    Granularity='MONTHLY',
                    Metrics=[
                        'UnblendedCost',
                    ],
                    GroupBy=GroupBy,
                    NextPageToken=nextToken
                )
                results.extend(response['ResultsByTime'])
                if 'nextToken' in response:
                    nextToken = response['nextToken']
                else:
                    nextToken = False
        # Now we should have all records, lets setup a waterfall datagrid
        #{key:value for (key,value) in dictonary.items()}
        rows = []
        for v in results:
            row = {'date':v['TimePeriod']['Start']}
            for i in v['Groups']:
                key = i['Keys'][0]
                if key in self.accounts:
                    key = self.accounts[key][ACCOUNT_LABEL]
                row.update({key:float(i['Metrics']['UnblendedCost']['Amount'])})
            if not v['Groups']:
                row.update({'Total':float(v['Total']['UnblendedCost']['Amount'])})
            rows.append(row)

        df = pd.DataFrame(rows)#index=[i['date'] for i in rows]
        df.set_index("date", inplace= True)
        df = df.fillna(0.0)

        if Style == 'Change':
            dfc = df.copy()
            lastindex = None
            for index, row in df.iterrows():
                if lastindex:
                    for i in row.index:
                        try:
                            df.at[index,i] = dfc.at[index,i] - dfc.at[lastindex,i]
                        except:
                            logging.exception("Error")
                            df.at[index,i] = 0
                lastindex = index
        df = df.T

        self.reports.append({'Name':Name,'Data':df})


    def generateExcel(self):
        # Create a Pandas Excel writer using XlsxWriter as the engine.\
        os.chdir('/tmp')
        writer = pd.ExcelWriter('cost_explorer_report.xlsx', engine='xlsxwriter')
        workbook = writer.book
        for report in self.reports:
            report['Data'].to_excel(writer, sheet_name=report['Name'])
            worksheet = writer.sheets[report['Name']]


            # Create a chart object.
            chart = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})

            chartend=12
            if CURRENT_MONTH:
                chartend=13
            for row_num in range(1, len(report['Data']) + 1):
                chart.add_series({
                    'name':       [report['Name'], row_num, 0],
                    'categories': [report['Name'], 0, 1, 0, chartend],
                    'values':     [report['Name'], row_num, 1, row_num, chartend],
                })

            worksheet.insert_chart('O2', chart)
        writer.save()

        #Time to deliver the file to S3
        if os.environ.get('S3_BUCKET'):
            s3 = boto3.client('s3')
            s3.upload_file("cost_explorer_report.xlsx", os.environ.get('S3_BUCKET') + customerName + '/', "cost_explorer_report.xlsx")
        if os.environ.get('SES_SEND'):
            #Email logic
            msg = MIMEMultipart()
            msg['From'] = os.environ.get('SES_FROM')
            msg['To'] = COMMASPACE.join(os.environ.get('SES_SEND').split(","))
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = customerName + "Cost Explorer Report"
            text = "Find your Cost Explorer report attached\n\n"
            msg.attach(MIMEText(text))
            with open("cost_explorer_report.xlsx", "rb") as fil:
                part = MIMEApplication(
                    fil.read(),
                    Name="cost_explorer_report.xlsx"
                )
            part['Content-Disposition'] = 'attachment; filename="%s"' % "cost_explorer_report.xlsx"
            msg.attach(part)
            #SES Sending
            ses = boto3.client('ses', region_name=SES_REGION)
            result = ses.send_raw_email(
                Source=msg['From'],
                Destinations=os.environ.get('SES_SEND').split(","),
                RawMessage={'Data': msg.as_string()}
            )


def main_handler(event, context=None):
    # -----------------------------------------------------------------------
    # initiating a session using ARN of the IAM role
    # -----------------------------------------------------------------------
    stsclient = boto3.client('sts')
    rolearn = event['ARN']
    roleExternalId = event['externalId']
    awsaccount = stsclient.assume_role(
        RoleArn=rolearn,
        ExternalId=roleExternalId,
        RoleSessionName='awsaccount_session'
    )
    ACCESS_KEY = awsaccount['Credentials']['AccessKeyId']
    SECRET_KEY = awsaccount['Credentials']['SecretAccessKey']
    SESSION_TOKEN = awsaccount['Credentials']['SessionToken']
    # ------------------------------------------------------------------------
    # get friendly name of customer
    # ------------------------------------------------------------------------
    customerName = event['customerName']
    costexplorer = CostExplorer(ACCESS_KEY=ACCESS_KEY, SECRET_KEY=SECRET_KEY, SESSION_TOKEN=SESSION_TOKEN, CurrentMonth=False)
    #Default addReport has filter to remove Credits / Refunds / UpfrontRI
    costexplorer.addReport(Name="Total", GroupBy=[],Style='Total')
    costexplorer.addReport(Name="TotalChange", GroupBy=[],Style='Change')
    costexplorer.addReport(Name="TotalInclCredits", GroupBy=[],Style='Total',NoCredits=False)
    costexplorer.addReport(Name="TotalInclCreditsChange", GroupBy=[],Style='Change',NoCredits=False)
    costexplorer.addReport(Name="Credits", GroupBy=[],Style='Total',CreditsOnly=True)
    costexplorer.addReport(Name="RIUpfront", GroupBy=[],Style='Total',UpfrontOnly=True)

    costexplorer.addRiReport(Name="RICoverage")
    costexplorer.addReport(Name="Services", GroupBy=[{"Type": "DIMENSION","Key": "SERVICE"}],Style='Total')
    costexplorer.addReport(Name="ServicesChange", GroupBy=[{"Type": "DIMENSION","Key": "SERVICE"}],Style='Change')
    costexplorer.addReport(Name="Accounts", GroupBy=[{"Type": "DIMENSION","Key": "LINKED_ACCOUNT"}],Style='Total')
    costexplorer.addReport(Name="AccountsChange", GroupBy=[{"Type": "DIMENSION","Key": "LINKED_ACCOUNT"}],Style='Change')
    costexplorer.addReport(Name="Regions", GroupBy=[{"Type": "DIMENSION","Key": "REGION"}],Style='Total')
    costexplorer.addReport(Name="RegionsChange", GroupBy=[{"Type": "DIMENSION","Key": "REGION"}],Style='Change')
    if os.environ.get('COST_TAGS'): #Support for multiple/different Cost Allocation tags
        for tagkey in os.environ.get('COST_TAGS').split(','):
            tabname = tagkey.replace(":",".") #Remove special chars from Excel tabname
            costexplorer.addReport(Name="{}".format(tabname)[:31], GroupBy=[{"Type": "TAG","Key": tagkey}],Style='Total')
            costexplorer.addReport(Name="Change-{}".format(tabname)[:31], GroupBy=[{"Type": "TAG","Key": tagkey}],Style='Change')
    costexplorer.generateExcel()
    return "Report Generated"

if __name__ == '__main__':
    main_handler()