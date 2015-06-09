# monitoring-nagios

A test harness to query multiple endpoints and roll up monitoring errors into a single alert for Nagios

## Overview

The script queries application metadata containing a tag for the application and an array of endpoints. Each endpoint url executes
is an application test returning an HTTP 200 status code upon success. If an endpoint fails, the test harness will roll up
any errors based on the level defined in the metadata. Output is printed to stdout for Nagios, including the error message,
tags, and level.

## Usage

For usage details:

	python app-monitor.py

## Metadata Format

	{
		"tag": "myapp",
		"endpoints":[
			{
				"name": "endpoint-test1",
				"url": "/path/to/service/test",
				"level": "warning",
				"tags": "service-tag",
				"timeout": 30
			}, {
				"name": "endpoint-test2",
				"url": "/path/to/service/test2",
				"level": "critical",
				"tags": "service-tag1,service-tag2"
			} 
		]
	}
