# REC.IO v2 – Final Snapshot & Onboarding Package

## Purpose
This package contains the complete v2 system snapshot from the system architect and all BMAD onboarding documentation. It is the **single source of truth** for understanding, operating, and supporting REC.IO v2 prior to the launch of v3.

> **🚨 CRITICAL SAFETY NOTICE:**  
> **NO AI AGENTS OR TEAM MEMBERS ARE PERMITTED TO PLACE LIVE TRADES FOR TESTING OR ANY OTHER PURPOSES.**  
> **NO AI AGENTS OR TEAM MEMBERS ARE PERMITTED TO ENABLE AUTOMATED TRADING FUNCTIONS FOR TESTING OR ANY OTHER PURPOSES.**  
> All testing must be performed in **read-only** or **simulation** modes only.

---

## 📂 Folder Structure & Documentation Index

### 01_Architecture_Map/
- `notes.md` – Architect's raw v2 architecture notes
- `System_Overview.md` – High-level architecture & service flow
- `Component_Level_Documentation.md` – Detailed per-service description with purpose, inputs/outputs, error behavior, dependencies, startup/shutdown sequence, and failure recovery steps
- `Frontend_Enhancements_Documentation.md` – Comprehensive frontend interface documentation including desktop/mobile interfaces, system monitoring, and admin controls
- `v2_current_architecture.png` – Current architecture diagram (to be created)
- `v3_target_architecture.png` – Target v3 architecture diagram (to be created)
- `v2_data_flow.png` – Data flow diagram (to be created)

### 02_Config/
- `MASTER_PORT_MANIFEST.json` – Canonical port assignments
- `config.json` – Global paths & settings
- `Port_and_Path_Configuration_Reference.md` – Human-readable reference for ports/paths/env

### 03_Database_Schemas/
- `postgresql_schema.sql` – Live DB schema
- `Database_Schema_and_Migration_Plan.md` – PostgreSQL migration plan & legacy cleanup steps

### 04_Infrastructure/
- `Deployment_Playbook.md` – Deploy/rollback procedures
- `CI_CD_and_Container_Guide.md` – Local-first → DigitalOcean pipeline
- `DigitalOcean_Deployment_Guide.md` – Complete DigitalOcean deployment guide with environment setup, deployment procedures, rollback mechanisms, and maintenance
- `Performance_Baselines.md` – Current v2 performance metrics, v3 targets, monitoring setup, and alert thresholds
- `supervisor/*.conf` – Process management configs

### 05_Security/
- `Secrets_Management_Policy.md` – Secrets handling & rotation procedures
- `Disaster_Recovery_Plan.md` – Recovery steps for DB/service/API/deploy failures

### 06_Strategy_and_Product_Logic/
- `Trade_Strategy_Book.md` – HOURLY HTC strategy & v3 multi-strategy vision
- `Feature_Roadmap.md` – Development priorities
- `Known_Issues_and_Design_Constraints.md` – Technical debt & brittle areas
- `Partner_Onboarding_Guide.md` – New team/stakeholder onboarding procedures

### 07_API_Contracts/
- `Kalshi_REST_and_WebSocket.md` – Complete Kalshi API contract with endpoints, authentication, examples, error codes, and retry logic
- `Coinbase_Symbol_Feed.md` – Comprehensive Coinbase API contract for symbol feed integration
- `Third_Party_Services.md` – Additional third-party services API contracts and integration patterns

---

### Root Files
- `Ownership_Assignment_and_AI_Prompt_Index.md` – Document owners & approved AI prompts
- `README.md` – This index

---

## Usage Guidelines
- **Reference First** – All production actions should be guided by these docs
- **Review Before Change** – Any code/config change must be reflected in relevant doc
- **Follow Safety Rules** – Absolutely no AI/agent live trade execution or automation enabling for testing

---

## Review & Maintenance
- Owners are responsible for quarterly review of their assigned docs
- All updates must be reviewed by Eric before merging to `main`
