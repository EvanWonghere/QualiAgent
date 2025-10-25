# **QualiAgent**

### 🧠 A Lightweight Assistant for Qualitative Analysis

QualiAgent helps researchers and students organize, code, and analyze qualitative data (e.g., interview transcripts, memos) using modern AI models — while staying light, transparent, and local-first.

------

## 🚀 **Start-Up Plan: Lightweight Code Stack**

- **Backend:** FastAPI (or Flask) with just a few clean endpoints.
- **Frontend:** Streamlit or Gradio for quick iteration — no heavy JS frameworks.
- **Database:** Initially SQLite (or simple `.json` / `.csv` files for prototyping).
- **AI Integration:**
  - GPT-4/5 (for analytical insights and coding assistance).
  - OpenAI Embeddings for semantic search and clustering.

------

## ⚙️ **Current Features**

Upload a text file (e.g., transcript, memo) → the system automatically chunks and analyzes it.
 Users can then manually create and manage **codes** and **memos**, which are stored in a local database for persistence and retrieval.

### ✅ **Core Capabilities**

- Upload and store **transcripts** and **memos**.
- Manually or automatically **create codes and memos** linked to text excerpts.
- Retrieve, edit, and delete items via RESTful API.
- Configure AI parameters (API URL, LLM model, embedding model, chunk size).

------

## 🧩 **Current Progress & Next Steps**

### **Step 1: Add “Codes” Feature** ✅ *(Done)*

**Goal:** Let users highlight meaningful text in transcripts/memos and assign a “code” — a short descriptive label.

#### Data Model

```json
{
  "id": "auto_generated",
  "code": "Identity Conflict",
  "excerpt": "I felt like I was between two cultures...",
  "source": "Transcript #1",
  "created_at": "...",
  "user_id": "..."
}
```

#### Backend Endpoints

- `POST /codes` → Create a code
- `GET /codes` → Retrieve all codes
- `DELETE /codes/{id}` → Delete a code

#### Frontend (planned)

- Sidebar panel for **Codes**
- Select text → “Add Code” option
- Code list view

------

### **Step 2: Add “Categories” Feature** ⏳ *(Next Step)*

**Goal:** Group related codes under broader categories.

#### Example

```
Category: Identity
 ├─ Identity Conflict
 ├─ Cultural Belonging
 └─ Hybrid Identity
```

#### Data Model

```json
{
  "id": "auto_generated",
  "category": "Identity",
  "codes": ["Identity Conflict", "Cultural Belonging"]
}
```

#### Planned Endpoints

- `POST /categories`
- `GET /categories`
- `PUT /categories/{id}` → Add/remove codes
- `DELETE /categories/{id}`

#### Planned Frontend

- Drag & drop grouping of codes.
- Collapsible category trees.

------

### **Step 3: Visualization Tools** ⏳ *(Planned)*

Once categories are in place, add analytical and visual tools such as:

- Code frequency charts (bar/pie).
- Code co-occurrence networks.
- Timeline visualization (codes over transcript time).

------

## 🧭 **Todo List**

1. Implement “Categories” system.
2. Build simple visualization module.
3. Update and version-control the database schema.
4. Integrate automatic coding suggestions from LLM (optional).
5. Polish UI and interaction in Streamlit/Gradio.

------

## 💡 **Vision**

A minimal, modular tool that brings the power of AI into qualitative research — while keeping full transparency and user control.