Get started:

    pip install tornado
    cd src
    ./main.py

Using virtualenv:

    # Setup virtualenv and install dependencies
    virtualenv .venv
    . .venv/bin/activate
    pip install tornado

    # Run the service
    cd src
    ./main.py


Components:

* `main.py`: the main script
* `config.py`: settings
* `logutils.py`: helper for pretty and easy logging to stdout and file
* `server.py`: TCP server and connection handler


Messages from the client:

{"type":"JOIN","crypto_params": {"identityString": "XXX","publicKey": "XXX","preKeyList": "XXX","signedPreKeyList": "XXX"}}

{"type":"SEARCH"}

{"type":"CHAT", "message":  {"internalType": "kexMessage", "message": "xxxx"}}
{"type":"CHAT", "message":  {"internalType": "encryptedMessage", "message": "xxxx"}}
