# Northline Industrial Systems Customer FAQ

Document Number: GL-SVC-2024-011
Version: V5.0
Maintenance Department: Customer Service Center
Update Date: January 10, 2025

## Section One: Ordering and Delivery

### Q1: What is the standard delivery cycle for the GTE-3000?

When standard models have sufficient stock, the goods will be shipped within 3 working days after payment. GTE-3000Pro and custom configurations are produced on order, with a delivery cycle of 15 working days. Bulk orders exceeding 100 units will have a delivery cycle confirmed separately.

### Q2: What accessories are included in the shipment?

The standard packaging includes: 1 gateway host, 1 24V/2A power adapter, 1 DIN rail clip set, 1 3-pin power terminal, 2 serial port terminals (4 for GTE-3000S and GTE-3000Pro), 1 quick start guide, 1 certificate of conformity. Antennas are optional accessories, and 4G/5G models come with 1 suction cup antenna by default.

### Q3: Can I try before purchasing?

Support is available. Potential customers can apply for a 30-day trial, which requires submitting a trial application form and approval from a sales manager. During the trial period, the equipment ownership belongs to the company, and it must be returned within 7 days after the trial or converted into a purchase. The shipping costs for trial equipment are borne by the customer, and the shipping costs can be deducted from the payment upon conversion to a purchase.

### Q4: Can a VAT special invoice be issued?

Yes. After the customer provides the invoicing information (company name, taxpayer identification number, address and phone number, bank account and number), a 13% VAT special invoice will be issued either with the goods or within 5 working days after receiving the payment.

## Section Two: Warranty and Maintenance

### Q5: What is the warranty period for the equipment?

The entire GTE series is guaranteed for 24 months from the date of manufacture. The warranty period for power adapters, antennas, and other accessories is 12 months. The warranty period is based on the manufacturing date on the equipment's nameplate. If the customer can provide valid purchase proof, the warranty period can be extended from the purchase date, with a maximum extension of 3 months.

### Q6: What situations are not covered by the warranty?

The following situations are not covered by the warranty and will be handled as paid repairs:

- Beyond the warranty period
- Improper use as per the manual, such as input voltage exceeding the DC 9V~36V range causing damage
- Self-disassembly, modification, or broken seal
- Damage caused by water immersion, fire, lightning, earthquakes, etc., which are force majeure events
- Obvious mechanical damage to the casing, such as structural deformation caused by dropping
- Faults caused by using non-Northline Industrial Systems firmware or third-party unauthorized software

### Q7: How to report a device malfunction?

Choose any of the following three methods:

1. Call the service hotline at 416-555-0147, from 8:30 to 20:30 on weekdays, and 9:00 to 18:00 on holidays
2. Submit an online service ticket on the Northline Industrial Systems official website under the [Service Support] section
3. Contact the assigned sales manager or after-sales engineer

When reporting a repair, please provide the device serial number (SN), description of the fault phenomenon, time of fault occurrence, and on-site photos or log files. The serial number is located on the device's side panel, with the format GL3000-YYWW-XXXXX.

### Q8: How long does the repair usually take?

Repair method: After the customer sends the device, we will complete the inspection and repair within 5 working days and return it. The round-trip shipping costs during the warranty period are covered by the company, while customers are responsible for the shipping costs outside the warranty period.

On-site service method: This is only applicable to customers who have purchased the on-site service package or projects with a single purchase of more than 50 units. In major service cities, the service team will arrive on-site within 24 hours, while in regional business destinations, it will arrive within 48 hours.

### Q9: Can a spare device be borrowed?

Customers who have signed an annual service agreement can apply for borrowing a spare device, with a maximum borrowing period of 15 days. The spare device is of the same or higher model, and the configuration during the borrowing period will be assisted by our engineers. A daily usage fee of 1% of the original device price will be charged if the device is not returned on time.

## III. Installation and Commissioning

### Q10: What should I do if I forget the device management port IP?

Press the RESET button on the device panel for more than 10 seconds to restore the device to factory settings. The management port IP will be restored to 192.168.1.10, with the default account admin and default password Gl@2024. Restoring to factory settings will clear all point configuration. Please try other methods first to recover the IP, such as using a network scanning tool to find the device with the MAC prefix 8C:1F:64 in the network segment.

### Q11: How to troubleshoot RS485 communication timeout?

Follow the steps below to troubleshoot:

1. Confirm that the A and B lines are not reversed; reversed connections result in no response at all.
2. Confirm that the serial port parameters match those of the slave device, especially the baud rate, data bits, stop bits, and parity.
3. Confirm that the slave address is correct, with Modbus slave address ranging from 1 to 247.
4. Confirm that 120Ω terminal resistors are connected at both ends of the bus, and they must be connected if the distance exceeds 300 meters.
5. Confirm that the device's PE terminal is grounded. In environments with many variable frequency drives, interference is strong, and grounding is essential to prevent data loss.
6. Use the [Running Monitoring]→[Communication Quality] panel to check the response time and timeout rate to determine if the issue is with all slaves or individual slaves.

### Q12: What should I do if the platform does not receive data after uploading?

First, check the connection status on the [Data Forwarding] page. A status of "Connected" indicates normal network and authentication, with issues likely in topic mapping or platform-side subscription. A status of "Reconnecting" suggests network or certificate problems; check if the device can ping the platform domain name, whether the certificate has expired, and whether the system time is accurate. A system time deviation of more than 5 minutes can cause TLS handshake failure.

### Q13: Can point configurations be imported in bulk?

Yes. Download the Excel template from [Device Management]→[Point Management], fill in the point name, register address, data type, scaling factor, and unit fields according to the template, and then import. Single imports should not exceed 5000 rows; if exceeded, import in batches. The system will perform format validation before import, and rows that fail validation will be highlighted in red with the reason. Correct the issues and re-import.

## IV. Faults and Alarms

### Q14: What does the error code ERR-5021 mean?

ERR-5021 indicates incompatibility between point configuration and the protocol stack, commonly occurring after cross-major version firmware upgrades. The solution is to roll back to the firmware version before the upgrade, and follow the instructions in the [Firmware Upgrade and Version Release Notes] to first upgrade to the transitional version before the target version.

### Q15: Why does the device frequently restart?

The three most common reasons are:

1. Unstable power supply. Use a multimeter to measure the input voltage; if it is below 9V, the device will power off and restart. Prioritize checking the power adapter and line voltage drop.
2. High ambient temperature. Long-term temperatures above 60°C will trigger a protection restart. Check if the installation location is near a heat source and if the cabinet has proper ventilation.
3. High memory usage by edge rules or models. When the GTE-3000Pro runs more than three models simultaneously, it may trigger memory protection. Reduce the number of models.

### Q16: Will data be lost during network disconnection?

No, data will not be immediately lost. During network disconnection, data is stored in local cache. The GTE-3000 can cache up to 100,000 entries, the GTE-3000S up to 500,000 entries, and the GTE-3000Pro up to 5,000,000 entries. Data is automatically transmitted once the network is restored. Data is only discarded in a first-in-first-out manner when the cache is full and the network is not restored.

## V. Account and Security

### Q17: What should I do if I forget the Web management password?

Guest password cannot be recovered, so the device must be reset via factory reset. Operator and visitor account passwords can be reset by the administrator via [System Maintenance]→[User Management]. It is recommended to retain at least two administrator accounts during deployment.

### Q18: What security reinforcement measures does the device support?

Telnet and FTP are disabled by default at factory release, only HTTPS and SSH are open. Additional reinforcement measures include: changing the default SSH port, disabling SSH password login and using keys instead, enabling mutual certificate authentication for northbound MQTT, assigning accounts by role to avoid shared administrator access, and regularly downloading and archiving logs via [System Maintenance].

### Q19: Does the firmware upgrade automatically?

No. The device does not perform automatic upgrades. All upgrades must be manually triggered via the Web interface or device management platform to avoid unexpected interruption of data collection during production hours.

## Six. Others

### Q20: What certifications does the product have?

GTE series has obtained CE, FCC, and RoHS certifications. Confirm region-specific wireless approvals with the sales manager before deployment. Certification documents can be obtained in electronic format from the sales manager.

### Q21: Is the old model GTE-2000 still available for purchase?

GTE-2000 was discontinued in December 2023. Currently, only spare parts and repair support are provided, with support until December 2026. New projects are recommended to directly select the GTE-3000 series. Point configuration files can be migrated from GTE-2000 to GTE-3000 via conversion tools.

### Q22: Can secondary development interfaces be provided?

Yes. The device provides two ways for integration: RESTful API and OPC UA Server. API documentation can be downloaded from the official website's [Developer] section. GTE-3000Pro also supports deploying custom containers, which requires signing a technical cooperation agreement for access permissions to be opened by us.
