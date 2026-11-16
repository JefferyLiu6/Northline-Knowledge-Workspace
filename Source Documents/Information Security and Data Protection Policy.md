# Northline Industrial Systems Inc. Information Security and Data Protection Policy

Document number: GL-SEC-2024-003
Version: V2.8
Effective date: November 1, 2024
Department of Jurisdiction: Information Technology Department

## Chapter One General Provisions

Article One To protect the company's information assets and customer data security, prevent information leakage, tampering, and loss, based on the "company security policy", "company data-handling policy", and "company privacy policy", and in combination with the company's actual situation, this regulation is formulated.

Article Two This regulation applies to all company employees, interns, outsourced personnel, and third-party personnel who need to access the company's information systems for business purposes.

Article Three Information security follows the principle of "whoever is in charge is responsible, whoever uses it is responsible." The Information Technology Department is responsible for technical measures and daily supervision, and the department heads are the first responsible persons for information security in their respective departments.

## Chapter Two Information Asset Classification

Article Four The company's information assets are divided into four levels based on their sensitivity:

**Top Secret**: Core source code, firmware signature private keys, unpublished product design drawings, merger and financing materials. Access is limited to personnel on the authorized list, and all access activities are recorded.

**Secret**: Customer lists and contact information, contracts and quotations, employee salary data, production process parameters, and customer site point configuration files. Access is granted based on job positions.

**Internal**: Internal management systems, meeting minutes, project weekly reports, and training materials. All employees can access these, and they must not be disseminated externally.

**Public**: Product brochures, publicly released technical manuals, official website content, and news releases. No access restrictions apply.

Article Five The creator of a file is responsible for marking the classification level. Files without a marked level are treated as "Internal" by default. If a change in classification level is needed, the original creator must propose it, and the department head must approve.

## Chapter Three Accounts and Permissions

Article Six When employees are hired, the Information Technology Department opens accounts based on their positions, including domain accounts, OA, email, code repositories, and production systems. Accounts follow the principle of minimal permissions, granting only the permissions necessary to perform job duties.

Article Seven Accounts must be real-name based, and sharing or lending of accounts is strictly prohibited. Security incidents caused by shared accounts will be the responsibility of the account owner.

Article Eight Password requirements: Length must be at least 12 characters, including at least three of the following four categories: uppercase letters, lowercase letters, numbers, and special characters. Passwords must not use names, birthdays, employee numbers, or consecutive characters. Passwords must be changed every 90 days, and the new password must not be the same as the previous five.

Article Nine Systems involving Top Secret and Secret assets must enable two-factor authentication. Remote access to the company's internal network must be through a VPN, and the VPN must enforce two-factor authentication.

Article Ten Permission changes: Within three working days after an employee transfers positions, the original department must submit a permission revocation request. All accounts must be frozen on the day of departure and deleted after 30 days. The Information Technology Department conducts a permission review quarterly to clean up zombie accounts and excessive permissions.

## Chapter Four Terminal and Network Security

Article Eleven All office terminals must install the company's unified terminal management software and antivirus software, and uninstallation or deactivation is prohibited. System patches must be installed within 30 days of release, and high-risk vulnerability patches must be installed within 7 days.

Article Twelve Terminals must enable disk encryption and screen lock, with a screen lock time not exceeding 10 minutes. Notebook computers must be carried with the user when leaving the office area and must not be left in a car or unattended.

Article Thirteen Without approval, it is prohibited to install cracked software, unknown-source tools, or remote control software on office terminals. If such software is required for R&D debugging, an application for a whitelist must be submitted to the Information Technology Department.

Article Fourteen USB storage devices are default disabled. If necessary, apply for access and use the company's uniformly issued encrypted USB drives. If an encrypted USB drive is lost, it must be reported within 24 hours.

Article Fifteen The office network, production network, and guest network are physically or logically isolated. The guest Wi-Fi only provides internet access and cannot access any internal systems. Production network devices must not be directly connected to the internet; external network access must be through a bastion host or industrial firewall proxy.

## Chapter Five Data Protection

Article Sixteen The collection of customer data follows the principle of minimal necessity, collecting only the fields necessary for business. Before collection, the purpose must be informed, and authorization must be obtained.

Article Seventeen The point configuration files and operation logs from customer sites are classified as Secret assets. After export, they must be stored in the company's designated encrypted storage space and must not be stored in personal cloud drives, personal emails, or personal messaging apps.

Article Eighteen Data transmission: Data at the Secret level or higher must be encrypted when transmitted externally. When sending emails, use an encrypted compressed package, and inform the recipient of the password through another channel. The use of unapproved third-party file transfer tools is prohibited.

Article 19 Data backup: The core business system is backed up by incremental daily, full weekly backups, and the back-up data is stored off site for a period of not less than six months.

Article 20: Data Destruction: Before discarding storage media, physical destruction or irreversible erasure must be performed, executed and recorded by the Information Technology Department. Confidential paper documents must be shredded using a paper shredder and not directly discarded into trash bins.

Article 21: Personal information processing follows the "company privacy policy." Systems involving employee and customer personal information must record processing logs and retain them for no less than 3 years.

## Chapter 6: Development Security

Article 22: Source code is uniformly stored in the company's code repository, and uploading to public platforms like unapproved public repositories is prohibited. Engineering reviews third-party component requirements through the dependency approval process.

Article 23: Hardcoding of passwords, keys, and tokens is prohibited in code. Sensitive configurations are injected via a configuration center or environment variables, with access to the configuration center controlled by permissions and fully audited.

Article 24: Firmware signing private keys are stored in a hardware encryption device. Signing operations require two authorized persons to initiate. The private key must not be exported or copied to any terminal.

Article 25: Security testing must be completed before version release, including dependency component vulnerability scanning, static code scanning, and interface privilege escalation testing. Releases with high-risk issues unresolved are prohibited.

Article 26: Production environment data must not be directly used for development and testing. If necessary, data must be desensitized first, with the desensitization plan reviewed by the Information Technology Department.

## Chapter 7: Third-Party Management

Article 27: Before collaborating with third parties, a confidentiality agreement must be signed, clearly defining data usage scope, retention period, destruction requirements, and liability for breach.

Article 28: Outsourcing personnel accounts must be uniquely identified, with permissions limited to the project scope. Accounts must be immediately revoked after contract termination. Outsourcing personnel must not access classified assets.

Article 29: Third-party devices accessing the company network must first undergo security checks by the Information Technology Department, including patch status, antivirus software, and presence of malicious programs.

## Chapter 8: Security Incident Handling

Article 30: The following situations must be reported to the Information Technology Department within 1 hour: abnormal account login, terminal infected with virus or ransomware, leakage of confidential files, loss of devices or storage media, and clicking on suspicious phishing emails.

Article 31: Security incident handling process: Report → Isolate affected systems → Assess impact scope → Disposal and recovery → Review and output improvement measures. Major incidents must be reported to the General Manager by the Information Technology Department and reported to regulatory authorities as required by law within the specified time frame.

Article 32: Concealing or delaying reports leading to expanded losses will be handled strictly according to Article 30 of the Employee Handbook.

## Chapter 9: Training and Assessment

Article 33: New employee onboarding training includes an information security module. Employees who fail the assessment will not be confirmed as regular employees. All employees must participate in an annual information security refresher training, which includes phishing email simulations.

Article 34: The Information Technology Department organizes a full-company phishing email simulation every six months, with click-through rate included in departmental management assessment. Employees who fail twice consecutively will receive specialized training.

## Chapter 10: Supplementary Provisions

Article 35: This guideline is interpreted by the Information Technology Department. In case of conflict with national laws and regulations, the latter shall prevail.

Article 36: This guideline takes effect from the date of implementation, and the original "Information Security Management Measures" (GL-SEC-2022-003) is simultaneously abolished.
