# System administration guide

This document contains a short guide for the operational maintenance of the system SeisLabData system.


## Production environment

The SeisLabData system is operational at IPMA's internal network. Its main entrypoint for users is
by accessing the URL:

<https://seis-lab-data.ipma.pt>


### System components

The system is composed of the following services:

```mermaid
flowchart TD
    rev-proxy(1. reverse proxy)
    webapp(2. web application)
    db[(3. main system db)]
    proc-worker(4. processing worker)
    file-server(5. http file server)
    tile-server(6. map tiles server)
    auth-webapp(7. user authentication service)
    auth-db[(7.1. database for authentication service)]
    auth-worker(7.2. worker for authentication service)
    message-broker(10. message broker)
    arch[[11. archive mount]]
    rev-proxy --> webapp
    rev-proxy --> file-server
    rev-proxy --> tile-server
    rev-proxy --- auth-webapp
    auth-webapp <--> auth-db
    auth-webapp --> auth-worker
    auth-worker <--> auth-db
    webapp <--> db
    proc-worker <--> db
    webapp <--> message-broker
    message-broker <--> proc-worker
    arch --> file-server
    arch --> tile-server
    arch <--> proc-worker
```

#### 1. `reverse proxy` service

This service routes incoming HTTP requests to the appropriate handler. It performs the following
routing:

| Rule | Destination |
| ---- | ----------- |
| requests to `seis-lab-data.ipma.pt` | Routed to the `web application` service |
| requests to `auth.seis-lab-data.ipma.pt` | Routed to the `user authentication service` |
| requests to `arch.seis-lab-data.ipma.pt` | Routed to the `http file server` |
| requests to `seis-lab-data.ipma.pt/tiles` | Routed to the `map tiles server` |


##### Relevant configuration files


#### 2. `web application` service
#### 3. `main system db`


## Operational System Deployment


## Management operations

### seis-lab-data CLI tool

### start/stop the system
