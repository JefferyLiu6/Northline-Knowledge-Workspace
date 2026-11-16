# GTE-3000 Series Industrial Smart Gateway Technical Manual

Document Number: GL-PRD-2024-017
Version: V3.2
Models covered: GTE-3000, GTE-3000S, and GTE-3000Pro
Published by the Product Department, Northline Industrial Systems Inc.

## 1. Product Overview

The GTE-3000 Series is an industrial intelligent gateway launched by Northline Industrial Systems for discrete manufacturing and process industries. It is deployed between production line equipment and upper-level systems, responsible for protocol conversion, edge computing, and data cloud upload. The device adopts a fanless aluminum alloy casing design, supporting DIN rail mounting and wall mounting.

There are three models in the series, with consistent hardware platforms, and differences mainly lie in computing power, number of interfaces, and wireless capabilities:

| Model | Processor | Memory | Storage | Ethernet Port | Serial Port | Wireless | Typical Power Consumption |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GTE-3000 | Quad-core 1.2GHz | 2GB | 8GB eMMC | 2 × Gigabit | 2 × RS485 | None | 6.5W |
| GTE-3000S | Quad-core 1.2GHz | 4GB | 16GB eMMC | 4 × Gigabit | 4 × RS485/RS232 | 4G Full Network Coverage | 9.2W |
| GTE-3000Pro | Eight-core 1.8GHz | 8GB | 64GB eMMC | 4 × Gigabit | 4 × RS485/RS232 | 5G + Wi-Fi 6 | 15.8W |

GTE-3000 is the base model, suitable for small-scale data collection on a single production line; GTE-3000S adds 4G uplink and more serial ports, suitable for workshops without wired networks; GTE-3000Pro has local inference capabilities and can run lightweight vision detection models at the edge.

## 2. Environmental Parameters

| Project | Metric |
| --- | --- |
| Operating Temperature | -20℃ ~ +70℃ |
| Storage Temperature | -40℃ ~ +85℃ |
| Relative Humidity | 5% ~ 95%, No Condensation |
| Protection Level | IP40 (Can reach IP54 with dust cover kit) |
| Input Voltage | DC 9V ~ 36V, Standard 24V Power Adapter |
| Vibration Resistance | 5 ~ 500Hz,2Grms |
| Mean Time Between Failures | MTBF ≥ 100000 Hours |

When the installation site temperature is consistently higher than 60℃, a heat dissipation duct must be installed or the device must be moved out of the high-temperature area; otherwise, the processor will trigger frequency reduction protection, manifested as longer data collection cycles and increased data latency.

## 3. Interface Description

### 3.1 Power Interface

The left side of the device has a 3-pin Phoenix terminal, from left to right: V+, V-, PE. PE is the protective grounding; grounding is mandatory when there is significant electrical interference in the workshop, otherwise RS485 communication is prone to checksum errors.

### 3.2 Ethernet Ports

LAN1 is the default management port, with a factory IP of 192.168.1.10 and subnet mask 255.255.255.0. LAN2 is the default business port, configured as a DHCP client at factory settings. LAN3 and LAN4 on GTE-3000S and GTE-3000Pro can be configured as switch ports to cascade downstream devices.

When the management port IP is forgotten, hold the RESET button for more than 10 seconds to restore factory settings, returning the management port IP to 192.168.1.10. Restoring factory settings will clear all collected point configurations; make sure to export the configuration file before operation.

### 3.3 Serial Ports

RS485 uses a 2-pin terminal with A and B lines. Serial port parameters support 1200 ~ 115200bps, default 9600bps, 8 data bits, 1 stop bit, no parity check. A maximum of 32 slave devices can be connected on the same 485 bus, with 120Ω terminal resistors required at both ends of the bus. GTE-3000S and GTE-3000Pro have built-in terminal resistors that can be enabled via a dip switch.

### 3.4 Digital Input/Output

GTE-3000Pro provides 4 routes DI and 2 paths DO. DI enters for dry interfaces, DDO is a relay output with contact capacity 30VDC/2A. DO is often used to connect sound alarms to export signals when collecting breaks or threshold limits.

## 4. Protocol Support

Protocols supported by the device facing field equipment:

- Modbus RTU / Modbus TCP
- OPC UA Client
- Siemens S7(S7-200 Smart / S7-1200 / S7-1500)
- Mitsubishi MC Protocol (3E Frame)
- Omron FINS
- Mitsubishi FX Series Programming Port Protocol
- CNC Equipment's FOCAS Protocol (Only supported by GTE-3000Pro)

Protocols supported by the device facing upper-level systems:

- MQTT 3.1.1 / MQTT 5.0, supporting TLS encryption and mutual certificate authentication
- HTTP / HTTPS Active Reporting
- OPC UA Server
- Standard access to AWS IoT and Azure IoT platforms

GTE-3000 can be configured with a maximum of 2000 data points, GTE-3000S with 5000, and GTE-3000Pro with 20000. New data points exceeding the limit will be rejected, with a prompt on the web configuration page stating "Exceeded the current model's data point limit."

## 5. Data Collection and Reporting Mechanism

Collection tasks are organized by "Collection Groups." A collection group includes several data points, a collection cycle, and a reporting strategy. The minimum collection cycle is 100ms, maximum 3600s. Reporting strategies include three types:

**Periodic Reporting**: Pack the latest value and report it at fixed intervals, independent of the collection cycle configuration. Suitable for trend data, such as temperature, current.

**Change Reporting**: Report only when the value changes beyond the set deadband threshold. Suitable for state data, significantly reducing traffic. Deadband threshold supports absolute value and percentage formats.

**Hybrid Reporting**: Immediately report upon change, while also reporting once at a longer heartbeat cycle to ensure the upper system receives the latest value even if it missed the change event. Recommended for production environments.

Data is stored in local cache when the network is down. GTE-3000 has a cache capacity of 100,000 entries, GTE-3000S has 500,000, and GTE-3000Pro has 5,000,000. After network recovery, data is resent in chronological order, with a default transmission rate limit of 200 entries per second to avoid overwhelming the upper system. When the cache is full, the oldest data is discarded on a first-in-first-out basis.

## 6. Edge Computing

GTE-3000Pro supports running edge rules and lightweight models on the device.

Edge rules are written using a SQL-like syntax, for example:

```text
SELECT device_id, temperature
FROM stream
WHERE temperature > 85
```

After a rule is triggered, three types of actions can be initiated: reporting alarm messages, setting DO outputs, and calling write commands to downstream devices.

Model inference supports ONNX format, with model files not exceeding 200MB. Typical scenarios include initial screening for product appearance defects, filtering out clearly qualified images at the edge to only upload suspected defective images to the central system for re-examination, reducing upward bandwidth usage by over 80%.

## 7. Web Configuration Interface

Access via browser to `https://192.168.1.10`, default account admin, default password Gl@2024. Password must be changed upon first login, with a minimum of 10 characters and at least three of the following: uppercase letters, lowercase letters, numbers, and special characters.

Main functional areas:

- Runtime Monitoring: CPU, memory, storage usage, real-time status of each collection group
- Device Management: Adding, deleting, modifying, and querying field devices and data points, supporting Excel batch import
- Data Forwarding: Configuration and topic mapping for northbound connections
- Edge Rules: Rule writing and debugging
- System Maintenance: Firmware upgrades, configuration import/export, log download, time synchronization

Exported configuration files are in an encrypted .glcfg format. During import, the model and version are validated, and cross-model imports are rejected. Configurations from GTE-3000 can be imported into GTE-3000S, but not vice versa, due to the possibility of exceeding the lower model's data point limit with higher model data points.

## 8. Security Mechanism

The device defaults to disabling Telnet and FTP, only opening HTTPS and SSH. SSH default port is 22, which can be modified in the system maintenance page.

Supports three levels of user roles: administrators can perform all operations; maintenance personnel can view monitoring, download logs, and restart collection tasks, but cannot modify point configuration; visitors have read-only access.

Firmware packages are signed by Northline Industrial Systems. During device upgrades, the signature is verified, and if the signature is invalid, the upgrade is rejected and the original firmware is retained. The upgrade process takes approximately 3 to 5 minutes, during which data collection is interrupted. After the upgrade is complete, the device automatically restarts and restores the original configuration.

## 9. Typical Deployment Methods

**Single Machine Deployment**: One GTE-3000 connects to a PLC and instruments on a production line, and connects to the workshop switch via LAN2, with data reporting to the plant-level MES.

**Dual Machine Hot Standby**: Two GTE-3000S units are interconnected via a heartbeat line. The standby unit takes over within 5 seconds if the main unit fails. Point configuration is automatically synchronized from the main unit to the standby unit. Hot standby requires both devices to have the same model and firmware version.

**Cascade Deployment**: At the workshop level, multiple GTE-3000 units collect data nearby, and the data is aggregated to a GTE-3000Pro for edge computing and unified cloud upload, reducing the number of public network connections.

## 10. Selection Recommendations

- Less than 500 points, with wired network, no edge computing needs: GTE-3000
- 500 to 3000 points, no network cables on site, requires 4G uplink: GTE-3000S
- More than 3000 points, requires edge inference or CNC device connection: GTE-3000Pro

The point configuration format of all three devices is fully compatible. When upgrading from GTE-3000 to GTE-3000Pro later, export the configuration and import it directly, without needing to re-enter the points.
