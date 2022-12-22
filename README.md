# SDC AWS FSWatcher

This is a filewatcher system that can be configured to watch a directory for new files and then upload them to an S3 bucket. It also tags the objects with the creation and modified time, to keep that information on the cloud as well. This is useful for keeping a backup of files on the cloud, or for keeping a copy of files that are being created on a local machine. You also can configure the system to log the `CREATE`, `PUT` and `DELETE` events to a Timestream table, so you can keep track of the files that are being created, modified or deleted in near realtime. This will allow for extra visibility of the AWS SDC Pipeline from the SDC External Server to the S3 Bucket.

## Table of Contents
- [SDC AWS FSWatcher](#sdc-aws-fswatcher)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
    - [Requirements](#requirements)
    - [Setup](#setup)
  - [Usage](#usage)
    - [Adding files](#adding-files)
    - [Modifying files](#modifying-files)
  - [Logs](#logs)
  - [Uninstall](#uninstall)

## Installation
### Requirements
- Python 3.6+
- AWS CLI
- AWS SDC External Server
- AWS S3 Bucket
- AWS Timestream Table (optional)

### Setup
1. Clone the repository

    ```git clone git@github.com:dbarrous/sdc_aws_fswatcher.git```

2. Install the requirements

    ```pip install -r requirements.txt```

3. Verify your AWS CLI is configured with access keys (Optional)

    ```aws configure```

    Note: It must have access to the S3 bucket and Timestream table without MFA(if you want to use it)

4. Configure the `config.json` file with your `SDC_SYSTEM_USER`, `SDC_AWS_S3_BUCKET`, `SDC_AWS_WATCH_PATH`, `SDC_AWS_TIMESTREAM_DB`, `SDC_AWS_TIMESTREAM_TABLE`. 

    * `SDC_SYSTEM_USER` is the user that will be used to run the script. It must have access keys set up to the `SDC_AWS_S3_BUCKET`, `SDC_AWS_TIMESTREAM_DB` and `SDC_AWS_TIMESTREAM_TABLE` without MFA.

    * `SDC_AWS_S3_BUCKET` is the S3 bucket that will be used to store the files. (**Required**)

    * `SDC_AWS_WATCH_PATH` is the directory that will be watched for new files. (**Required**)

    * `SDC_AWS_TIMESTREAM_DB` is the Timestream database that will be used to store the logs. (*Optional*)

    * `SDC_AWS_TIMESTREAM_TABLE` is the Timestream table that will be used to store the logs. (*Optional*)
    
    * `SDC_AWS_PROFILE` is the AWS Profile to use for authentication. (*Optional*)

    * `SDC_AWS_CONCURRENCY_LIMIT` is the Concurrent uploads limit to S3. (*Optional*)

    * `SDC_AWS_ALLOW_DELETE` is a flag to Delete files from S3 if they are deleted from the watch directory. (*Optional*)

5. Run the install script

    ```sudo python install.py```

    Note: This will create a service called `sdc-aws-fswatcher` that will run the `sdc_aws_fswatcher.py` script on boot.

6. Verify the service is running

    ```sudo systemctl status sdc-aws-fswatcher.service```

    Note: If the service is not running/errored out, you can check the logs with `sudo journalctl -u sdc-aws-fswatcher.service -n 100`


## Usage
### Adding files
1. Add a file to the `SDC_AWS_WATCH_PATH` directory

    ```touch /path/to/SDC_AWS_WATCH_PATH/test.txt```

2. Verify the file was uploaded to the `SDC_AWS_S3_BUCKET` bucket

    ```aws s3 ls s3://SDC_AWS_S3_BUCKET/```

3. Verify the file was tagged with the creation and modified time

    ```aws s3api head-object --bucket SDC_AWS_S3_BUCKET --key test.txt```

4. Verify the file was logged to the `SDC_AWS_TIMESTREAM_TABLE` table (optional)

    ```aws timestream-query query --query-string "SELECT * FROM SDC_AWS_TIMESTREAM_DB.SDC_AWS_TIMESTREAM_TABLE"```

### Modifying files
1. Modify the file in the `SDC_AWS_WATCH_PATH` directory

    ```echo "test" >> /path/to/SDC_AWS_WATCH_PATH/test.txt```

2. Verify the file was uploaded to the `SDC_AWS_S3_BUCKET` bucket

    ```aws s3 ls s3://SDC_AWS_S3_BUCKET/```

3. Verify the file was tagged with the creation and modified time

    ```aws s3api head-object --bucket SDC_AWS_S3_BUCKET --key test.txt```

4. Verify the file was logged to the `SDC_AWS_TIMESTREAM_TABLE` table (optional)

    ```aws timestream-query query --query-string "SELECT * FROM SDC_AWS_TIMESTREAM_DB.SDC_AWS_TIMESTREAM_TABLE"```

## Logs
There are two ways to view the logs of the filewatcher system. You can view the logs in the directory which contains the script within the `hermes.log` file.

Or since it is installed as a service you can view the logs with `sudo journalctl -u sdc-aws-fswatcher.service -n 100` or by viewing the logs in the `/var/log/sdc-aws-fswatcher.log` file.

## Uninstall

1. Run the uninstall script

    ```sudo python uninstall.py```

2. Verify the service is not running

    ```sudo systemctl status sdc-aws-fswatcher.service```

    Note: If the service is running/errored out, you can check the logs with `sudo journalctl -u sdc-aws-fswatcher.service -n 100`



