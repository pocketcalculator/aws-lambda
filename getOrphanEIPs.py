import boto3
import datetime
import time
import os

stsclient = boto3.client('sts')
s3client = boto3.resource('s3')

def lambda_handler(event, context):

    # -----------------------------------------------------------------------
    # initiating a session using ARN of the IAM role
    # -----------------------------------------------------------------------
    roleARN = event['ARN']
    roleExternalId = event['externalId']
    awsaccount = stsclient.assume_role(
        RoleArn=roleARN,
        ExternalId=roleExternalId,
        RoleSessionName='awsaccount_session'
    )
    ACCESS_KEY = awsaccount['Credentials']['AccessKeyId']
    SECRET_KEY = awsaccount['Credentials']['SecretAccessKey']
    SESSION_TOKEN = awsaccount['Credentials']['SessionToken']
    # -----------------------------------------------------------------------
    # get friendly name of customer
    # -----------------------------------------------------------------------
    customerName = event['customerName']
    # -----------------------------------------------------------------------
    # create a list of all currently available aws regions
    # -----------------------------------------------------------------------
    ec2 = boto3.client('ec2', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY, aws_session_token=SESSION_TOKEN)
    final_awsregionslist = []
    awsregions = ec2.describe_regions()
    awsregions_list = awsregions['Regions']
    for region in awsregions_list:
        final_awsregionslist.append(region['RegionName'])
    # -----------------------------------------------------------------------
    start = '::'
    end = ':'
    awsaccountid = roleARN[roleARN.find(start)+len(start):roleARN.rfind(end)] # getting awsaccount ID from IAM Role ARN

    # -----------------------------------------------------------------------
    # Building HTML page/table using jquery datatables
    # -----------------------------------------------------------------------
    date_now = datetime.date.today()
    time_now = time.strftime("%H:%M:%S")
    creationdatetime = f'last update: {date_now} {time_now} UTC'
    payload_start = """<html><head><script src="https://code.jquery.com/jquery-3.3.1.min.js"></script><link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.16/css/jquery.dataTables.css"><script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.10.16/js/jquery.dataTables.js"></script><script>$(document).ready( function () {$('#example').DataTable();} );</script></head><body><table id="example" class="display"><thead><tr><th><font face="arial">AWS Account Id</font></th><th><font face="arial">AWS Region</font></th><th><font face="arial">EIP</font></th></tr></thead><tbody>"""

    # -----------------------------------------------------------------------
    # loop through all exisiting aws regions
    # -----------------------------------------------------------------------
    for awsregion in final_awsregionslist:
        # ===================  THIS IS WHERE YOUR JOB STARTS  ==================
        # ----------------------------------------------------------------------
        # Open ec2 session for current aws account (arn) and region
        ec2client = boto3.client('ec2', aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY, aws_session_token=SESSION_TOKEN, region_name=awsregion)

        # ----------------------------------------------------------------------
        response = ec2client.describe_addresses()
        elasticipslist = response['Addresses']
        for eip in elasticipslist:
            if 'AssociationId' not in eip:
                elastic_ip = eip['PublicIp']
                # --------------------------------------------------------------
                # Building HTML page/table
                loopstring = f'<tr><td><font face="arial">{awsaccountid}</font></td><td><font face="arial">{awsregion}</font></td><td><font face="arial">{elastic_ip}</font></td></tr>'
                payload_start = payload_start + loopstring
        payload_end = f'</tbody></table><p>{creationdatetime}</p></body></html>'
        finalpayload = payload_start + payload_end
        # --------------------------------------------------------------
        bucketPath = customerName + '/'
        htmlfilename = f'awsaccount-{awsaccountid}-EIPs.html'  # making unique name for HTML file
        if os.environ.get('S3_BUCKET'):
            domain = os.environ.get('S3_BUCKET')  # S3 bucket name where HTML page will be saved (must be changed)
            s3client.Object(domain, bucketPath + htmlfilename).put(Body=finalpayload, ContentType='text/html')
        else:
            print("No target S3 bucket identified so printing to stdout...")
            print(finalpayload)
        # ===================  THIS IS WHERE YOUR JOB ENDS  ===================
