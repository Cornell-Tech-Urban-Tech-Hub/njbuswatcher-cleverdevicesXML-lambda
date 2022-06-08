import json
from NJTransitAPI import get_xml_data, parse_xml_getBusesForRouteAll
import pandas as pd
import boto3
import datetime as dt
import os

# S3 settings
aws_region_name='us-east-2'
aws_bucket_name='bus-observatory' # data will be stored in a system_id bucket under this


def lambda_handler(event, context):
    
    ################################################################## 
    # configuration
    ################################################################## 
    
    # aws
    aws_bucket_name="busobservatory"
    aws_region_name="us-east-1"
    # aws_secret_name="LambdaDeveloperKeys"
    # aws_access_key_id = get_secret(aws_secret_name,aws_region_name)['aws_access_key_id']
    # aws_secret_access_key = get_secret(aws_secret_name,aws_region_name)['aws_secret_access_key']
    
    # system to track
    # store api key in secret api_key_{system_id}
    # e.g. api_key_nyct_mta_bus_siri
    system_id="njtransit_bus"

    ################################################################## 
    # fetch data
    ##################################################################   
 
    data, fetch_timestamp = get_xml_data('nj','all_buses')

    ################################################################## 
    # parse data
    ##################################################################

    positions = pd.DataFrame([vars(bus) for bus in parse_xml_getBusesForRouteAll(data)])
    positions['timestamp'] = fetch_timestamp
    positions = positions.drop(['name','bus'], axis=1) 
    positions[["lat", "lon"]] = positions[["lat", "lon"]].apply(pd.to_numeric)

    ################################################################## 
    # dump S3 as parquet
    ##################################################################   
          
    # dump to instance ephemeral storage 
    filename=f"{system_id}_{fetch_timestamp}.parquet".replace(" ", "_").replace(":", "_")
    
    # times'ms' per https://stackoverflow.com/questions/63194941/athena-returns-wrong-values-for-timestamp-fields-in-parquet-files
    positions.to_parquet(f"/tmp/{filename}", times='int96')

    # upload dump_file to S3
    source_path=f"/tmp/{filename}" 
    remote_path=f"{system_id}/{filename}"
    session = boto3.Session(region_name=aws_region_name)
    # session = boto3.Session(
    #     region_name=aws_region_name,
    #     aws_access_key_id=aws_access_key_id,
    #     aws_secret_access_key=aws_secret_access_key)
    s3 = session.resource('s3')
    result = s3.Bucket(aws_bucket_name).upload_file(source_path,remote_path)
    outpath = f"s3://{aws_bucket_name}/{remote_path}" 
    outmessage = f"njbuswatcher-cleverdevicesXML-lambda: Dumped {len(positions)} records to {outpath}"
    
    # clean up /tmp
    try:
        os.remove(source_path)
    except:
        pass

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": outmessage
        }),
    }