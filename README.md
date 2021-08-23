# StaticRegisterDashBoard
Static Register DashBoard is a tool to create a local copy of HTML of the Register Dashboard. Here is a example website [RegisterDashBoard](https://berdychrtk.github.io/RegisterDashboard/).

### Quick Start
```bash
git clone https://github.com/BerdychRTK/StaticRegisterDashBoard.git
cd StaticRegisterDashBoard

pip install -r requirements.txt

# must use python3.8 or above
python3.8 main.py ExcelFileOrJsonFile
```

### Formats
- support a proprietary register format using Excel
- support a JSON format with tree structure

### JSON

#### `example.json`
```javascript
{
    "name": "root",
    "id": "unique_id1",
    "children": [
        {
            "name": "SoC",
            "id": "unique_id_soc",
            "children": [
                {
                    "name": "uart",
                    "id": "unique_id_uart",
                    "children": [
                        {
                            "name": "baud_rate_register",
                            "id": "register_id_xxx",
                            "address": "0x1200",
                            "fields": [
                                {
                                    "bits": "15:0",
                                    "field": "baud_rate",
                                    "access": "RW",
                                    "default": "0x9600",
                                    "desc": "the baud rate setting"
                                },
                                ...
                            ]
                        }
                        ...
                    ]
                }
                ...
            ]
        },
    ]
}
```
### Leaf Node
A leaf node should be a `register` and must has following attributes
```javascript
// A register (leaf node)
{
    "name" : "register",
    "id" : "unique_id",
    "address": "0x1fc00000",  // must be HEX
    "fields": [
        // Register must be 32 bit wide.
        {
            "bits": "31:1",
            "field": "field_name",
            "access": "RW",
            "default": "0x0",  // must be HEX
            "desc": "field description",
        },
        ...
    ]
}
```

### Node (Parent Node)
```javascript
// A module (parent node)
{
    "name" : "module1",
    "id": "unique_id1",
    "children": [
        {
            // register ...
        },
        {
            // or another module
            "name": "module2",
            "id": "unique_id2",
            "children": [
                ...
            ]
        }

    ]
}
```

### Root
you can't use array as root index
```javascript
// Valid format
{
    "name": "root",
    "id": "root_id",
    "children": [
        ...
    ]
}

// this is invalid format
[  // <-- not allowed using array as root index
    {
        "name": "root0"
        ...
    },
    {
        "name": "root1"
        ...
    },
]
```
