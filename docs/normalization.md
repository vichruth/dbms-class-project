# EdgeDB: Formal Database Normalization Walkthrough
**Course:** Database Management Systems  
**Student:** Vichruth M (24BCE2300) · VIT Vellore  
**System:** EdgeDB — Offline-First Relational Data Synchronization Engine  

---

## 1. Introduction & Objectives
The central relational database in EdgeDB must guarantee absolute consistency, avoid update anomalies, and eliminate data redundancy across edge devices (smartphones, laptops, smartwatches). 

This document demonstrates the step-by-step mathematical decomposition of an unnormalized flat database schema into **First Normal Form (1NF)**, **Second Normal Form (2NF)**, **Third Normal Form (3NF)**, and **Boyce-Codd Normal Form (BCNF)**.

---

## 2. The Universal Unnormalized Relation (UNF)

Consider a naive schema where all edge transactions, device specifications, categorizations, and sync telemetry are stored in a single flat log table:

$$\text{UNF}(\underline{\text{DeviceUUID}}, \underline{\text{ClientBatchSeq}}, \underline{\text{ItemIndex}}, \text{DeviceName}, \text{DeviceType}, \text{DeviceSpecificHW}, \text{CategoryName}, \text{CategoryDesc}, \text{Amount}, \text{ExpenseDesc}, \text{EventTime}, \text{SyncTime})$$

### The Three Classical Anomalies in UNF:
1. **Insertion Anomaly:** We cannot register a new device (e.g., a newly paired smartwatch) or a new expense category without inventing a dummy expense transaction, because `ItemIndex` is part of the primary key.
2. **Deletion Anomaly:** If a user deletes the only expense record associated with the "Books & Education" category, the existence of the category and its description is completely erased from the database.
3. **Modification / Update Anomaly:** If the user renames their device or updates the device OS version, every single expense ever synchronized from that device must be updated. A partial update results in inconsistency.

---

## 3. First Normal Form (1NF)

### 1NF Definition:
A relation $R$ is in 1NF if and only if:
1. All underlying domains contain only **atomic (indivisible) values**.
2. There are no repeating groups or multi-valued arrays.
3. Each record is uniquely identifiable by a Primary Key.

### Transformation to 1NF:
In our edge device payload, multi-item batches and composite hardware strings are flattened into atomic scalar values.
- Primary Key: $\{\text{DeviceUUID}, \text{ClientBatchSeq}, \text{ItemIndex}\}$
- Candidate Key: $\{\text{DeviceUUID}, \text{ClientBatchSeq}, \text{ItemIndex}\}$

$$\text{R\_1NF}(\underline{\text{DeviceUUID}}, \underline{\text{ClientBatchSeq}}, \underline{\text{ItemIndex}}, \text{DeviceName}, \text{DeviceType}, \text{HardwareInfo}, \text{CategoryName}, \text{CategoryDesc}, \text{Amount}, \text{ExpenseDesc}, \text{EventTime}, \text{SyncTime})$$

### Functional Dependencies (FDs) in R_1NF:
- **FD1:** $\{\text{DeviceUUID}\} \rightarrow \{\text{DeviceName}, \text{DeviceType}, \text{HardwareInfo}\}$
- **FD2:** $\{\text{DeviceUUID}, \text{ClientBatchSeq}\} \rightarrow \{\text{SyncTime}\}$
- **FD3:** $\{\text{CategoryName}\} \rightarrow \{\text{CategoryDesc}\}$
- **FD4:** $\{\text{DeviceUUID}, \text{ClientBatchSeq}, \text{ItemIndex}\} \rightarrow \{\text{Amount}, \text{ExpenseDesc}, \text{CategoryName}, \text{EventTime}\}$

---

## 4. Second Normal Form (2NF)

### 2NF Definition:
A relation $R$ is in 2NF if and only if:
1. It is in 1NF.
2. **No non-prime attribute is partially dependent** on any candidate key. Every non-prime attribute must depend on the *entire* composite key.

### Identifying Partial Dependencies:
In $\text{R\_1NF}$, the composite candidate key is $K = \{\text{DeviceUUID}, \text{ClientBatchSeq}, \text{ItemIndex}\}$.
- In **FD1**, $\{\text{DeviceName}, \text{DeviceType}, \text{HardwareInfo}\}$ depends only on $\{\text{DeviceUUID}\}$, a proper subset of $K$. $\rightarrow$ **Partial Dependency!**
- In **FD2**, $\{\text{SyncTime}\}$ depends only on $\{\text{DeviceUUID}, \text{ClientBatchSeq}\}$, a proper subset of $K$. $\rightarrow$ **Partial Dependency!**

### Decomposition into 2NF:
We decompose $\text{R\_1NF}$ into three relations:

1. **DEVICE_2NF** $(\underline{\text{DeviceUUID}}, \text{DeviceName}, \text{DeviceType}, \text{HardwareInfo})$
   - Key: $\{\text{DeviceUUID}\}$
   - Governed by FD1.
2. **SYNC_BATCH_2NF** $(\underline{\text{DeviceUUID}}, \underline{\text{ClientBatchSeq}}, \text{SyncTime})$
   - Key: $\{\text{DeviceUUID}, \text{ClientBatchSeq}\}$
   - Governed by FD2.
3. **EXPENSE_2NF** $(\underline{\text{ExpenseID}}, \text{DeviceUUID}, \text{ClientBatchSeq}, \text{CategoryName}, \text{CategoryDesc}, \text{Amount}, \text{ExpenseDesc}, \text{EventTime})$
   - Key: $\{\text{ExpenseID}\}$ (surrogate key replacing the composite key).
   - Governed by FD4.

All partial dependencies have been removed.

---

## 5. Third Normal Form (3NF)

### 3NF Definition:
A relation $R$ is in 3NF if and only if:
1. It is in 2NF.
2. There are **no transitive dependencies** of non-prime attributes on the primary key ($X \rightarrow Y$ and $Y \rightarrow Z$ where $Z$ is not prime).

### Identifying Transitive Dependencies in EXPENSE_2NF:
In `EXPENSE_2NF`, we observe:
- $\text{ExpenseID} \rightarrow \text{CategoryName}$
- $\text{CategoryName} \rightarrow \text{CategoryDesc}$ (FD3)
- Therefore, $\text{ExpenseID} \rightarrow \text{CategoryDesc}$ is a **transitive dependency** through `CategoryName`.

If a category description changes, it must be updated in every expense row belonging to that category.

### Decomposition into 3NF:
We isolate the lookup entity into its own relation:

1. **CATEGORY** $(\underline{\text{CategoryID}}, \text{CategoryName}, \text{CategoryDesc})$
   - Key: $\{\text{CategoryID}\}$ and alternate key $\{\text{CategoryName}\}$
   - FD: $\text{CategoryID} \rightarrow \text{CategoryName}, \text{CategoryDesc}$
2. **EXPENSE** $(\underline{\text{ExpenseID}}, \text{DeviceID}, \text{CategoryID}, \text{Amount}, \text{ExpenseDesc}, \text{EventTime}, \text{Version})$
   - Key: $\{\text{ExpenseID}\}$
   - References `CATEGORY(CategoryID)` and `DEVICE(DeviceID)`.

---

## 6. Boyce-Codd Normal Form (BCNF)

### BCNF Definition:
A relation $R$ is in BCNF if and only if:
- For every non-trivial functional dependency $X \rightarrow Y$, **$X$ is a superkey**.

### Verification of EdgeDB Relations:

| Relation | Determinant ($X$) | Dependent ($Y$) | Is $X$ a Superkey? | BCNF Compliant? |
|---|---|---|:---:|:---:|
| `device` | `device_id` | `device_uuid, device_name, device_type` | Yes (PK) | **Yes** |
| `device` | `device_uuid` | `device_id, device_name, device_type` | Yes (Candidate Key) | **Yes** |
| `category` | `category_id` | `category_name, description` | Yes (PK) | **Yes** |
| `category` | `category_name`| `category_id, description` | Yes (Candidate Key) | **Yes** |
| `sync_batch` | `batch_id` | `device_id, client_batch_seq, received_at` | Yes (PK) | **Yes** |
| `sync_batch` | `{device_id, client_batch_seq}` | `batch_id, received_at, status` | Yes (Candidate Key) | **Yes** |
| `expense` | `expense_id` | `device_id, category_id, amount, description, event_time, version` | Yes (PK) | **Yes** |
| `activity_entry` | `activity_id` | `device_id, entry_date, step_count, version` | Yes (PK) | **Yes** |
| `activity_entry` | `{device_id, entry_date}` | `activity_id, step_count, version` | Yes (Candidate Key) | **Yes** |
| `conflict_log` | `conflict_id` | All audit attributes | Yes (PK) | **Yes** |

**Conclusion:** Every single determinant in our relational model is a superkey. The central database is in **BCNF**, completely free of functional dependency anomalies.

---

## 7. Enhanced ER (EER) Specialization

In addition to standard BCNF normalization, EdgeDB models hardware diversity via **Disjoint, Total Specialization**:

```
                 [ DEVICE ] (Supertype)
                     |
         +-----------+-----------+
         | (d, t)    |           |
         v           v           v
  [ PhoneDevice ] [ LaptopDevice ] [ WatchDevice ]
```

- **Table-per-Subtype Pattern**:
  - `phone_device` contains `(device_id PK/FK, os_version, imei)`
  - `laptop_device` contains `(device_id PK/FK, os_name, mac_address)`
  - `watch_device` contains `(device_id PK/FK, watch_model, firmware_version)`
- **Integrity**: `device_id` in each subtype is simultaneously a Primary Key and a Foreign Key referencing `device(device_id) ON DELETE CASCADE`.
- This avoids sparse NULL columns in the parent table while strictly preserving 3NF/BCNF.

