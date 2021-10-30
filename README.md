# redfish-inspector

This tool queries ironic for a list of node names, uuids, and BMC ip address and credentials

It will then use the redfish hardware inventory API to directly download .xml inventory files for each node.

This .xml file is parsed, and used to generate a referenceapi compatible json file for commit.

This is compatible with all Dell 14g servers, with others requiring testing.


## Installation

Install the tool via `poetry install`
## Usage
Make sure a valid `clouds.yaml` or openstack `OS_` env vars are set. This tool uses the same auth method as `openstackcli`.

The tool can be run by:
```
OS_CLOUD=<name_in_clouds.yaml> poetry run redfish-inspector
```

## TODO
specify output format and location

## Possible Enhancements

Directly generate info for doni hardware import
Populate ironic "properties"