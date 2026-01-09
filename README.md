# 🏥 Pulse Hospital Management System (Backend)

A comprehensive Hospital Management System (HMS) backend built with **Django** and **Django REST Framework (DRF)**. This system manages the entire workflow of a hospital, including OPD, IPD, OT, Pharmacy, and Billing, with role-based access for Doctors, Receptionists, and Admins.

It provides a robust REST API to serve mobile applications and frontend clients.

---

## 🚀 Key Features

### 1. 🔐 Authentication & Roles
* **Role-Based Access Control (RBAC):** Separate portals for Admin, Doctor, Receptionist, and Pharmacist.
* **Secure Login API:** Token-based authentication for mobile apps.
* **Auto-Redirect:** Smart login logic that detects user role (Superuser/Staff) and redirects to the correct dashboard.

### 2. 👩‍💼 Reception Management
* **Dashboard Stats:** Real-time view of Pending Appointments, Confirmed Visits, and Doctor Availability.
* **Patient Registration:** Auto-generation of unique Patient IDs (e.g., `MED-2026-001`, `GYN-2026-045`) based on the department.
* **Appointment Booking:** Schedule appointments for specific doctors.
* **Bed Management:** Live status of Beds (General/ICU) - Occupied vs Available.
* **Patient Discharge:** One-click discharge that automatically frees up the assigned bed.

### 3. 👨‍⚕️ Doctor Module (OPD & IPD)
* **Live Queue:** Real-time list of assigned patients for the day.
* **Digital Prescription:** Add diagnosis, symptoms, and medicines (dynamic list).
* **Patient History:** View past visits, vitals, and previous diagnoses.
* **Discharge Summary:**
    * Auto-fetches Admission & Patient details.
    * Detailed recording of Vitals, LFT/KFT, X-Ray/MRI/CT-Scan reports.
    * Treatment given and Advice on discharge.
* **OT Management:** Schedule Surgeries and add Post-Op notes.

### 4. 🛌 In-Patient Department (IPD)
* **Admission:** Admit patients to specific beds.
* **Daily Rounds:** Doctors/Nurses can add daily treatment records (Injection, Saline, Vitals).
* **Auto Bed Release:** Bed status automatically updates to "Available" upon discharge.

---

## 🛠️ Tech Stack

* **Backend Framework:** Django 4.x (Python)
* **API Framework:** Django REST Framework (DRF)
* **Database:** MySQL / SQLite (Default)
* **Authentication:** Token Authentication

---

## 🔌 API Documentation (Mobile/Frontend Endpoints)

The backend exposes the following REST APIs for mobile app integration.

### 🔐 Authentication
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/mobile/login/` | Returns Auth Token & User Role (`doctor`, `receptionist`, etc.) |

### 👩‍💼 Reception APIs
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/mobile/reception/dashboard/` | Get stats (Pending, Confirmed) & Doctor availability. |
| `POST` | `/api/mobile/reception/book/` | Book a new appointment. |
| `GET` | `/api/mobile/reception/beds/` | Get list of all beds with status (Occupied/Free). |
| `POST` | `/api/mobile/reception/discharge/<id>/` | Discharge a patient and release their bed. |
| `GET` | `/api/mobile/billing/search-patient/?search=xyz` | Search admitted patients by Name or ID. |

### 👨‍⚕️ Doctor APIs
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/mobile/doctor/dashboard/` | Get Doctor's profile, stats, and today's patient queue. |
| `GET` | `/api/mobile/doctor/checkup/<appt_id>/` | Fetch patient details and past history. |
| `POST` | `/api/mobile/doctor/checkup/<appt_id>/` | Save Diagnosis, Symptoms, and Medicine Prescription. |
| `POST` | `/api/mobile/doctor/discharge-summary/` | Create a detailed Discharge Summary. |
| `POST` | `/api/mobile/doctor/book-ot/` | Schedule a surgery (OT Booking). |
| `POST` | `/api/mobile/doctor/ot-notes/<ot_id>/` | Add surgery notes and mark status as 'Completed'. |

### 🛌 IPD APIs
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/mobile/ipd/daily-round/<admission_id>/` | Add daily treatment round (Injection/Saline/Vitals). |

---

## 🗄️ Database Models Overview

* **PatientProfile:** Handles unique Registration ID logic.
* **Appointment:** Links Patient to Doctor, stores symptoms & diagnosis.
* **IPD_Admission:** Links Patient to a `Bed` and tracks discharge status.
* **DischargeSummary:** Stores comprehensive clinical data (Snapshot of patient name/ID included).
* **OTBooking:** Manages Surgery schedules and Pre/Post-op notes.

---

## ⚙️ Installation & Setup

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/jayeshhsathawane/Pulse_Hospital_Management_System-website.git
    cd pulse-hospital-backend
    ```

2.  **Create Virtual Environment**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Mac/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Database Migrations**
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

5.  **Create Superuser (Admin)**
    ```bash
    python manage.py createsuperuser
    ```

6.  **Run Server**
    ```bash
    # For Local Development
    python manage.py runserver

    # For Mobile Testing (LAN)
    python manage.py runserver 0.0.0.0:8000
    ```

---

---

### Developed by [Your Name]
