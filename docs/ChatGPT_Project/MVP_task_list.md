# 🚀 **QualiAgent Project Task List**

🎯 **Goal**: Build a lightweight, memory-safe prototype enabling researchers to upload transcripts, manage them, generate AI-assisted insights (codes and memos), and perform semantic search.

------



### 🧩 Phase 1: Core Backend & Database (✅ Completed)



| **TASK**                | **DESCRIPTION**                                              | **STATUS** |
| ----------------------- | ------------------------------------------------------------ | ---------- |
| **Backend Framework**   | Set up a **FastAPI** server using dependency injection for database sessions. | ✅          |
| **Database Schema**     | Define **SQLite** database with **SQLAlchemy** models: `Transcript`, `Chunk`, `Memo`, `Code`. | ✅          |
| **Memory-Safe Uploads** | Implement an endpoint to stream uploads to a permanent `/uploaded_files` directory and store the `file_path` (not content) in the `Transcript` table. | ✅          |
| **Core API Routes**     | Implement all necessary CRUD (Create, Read, Update, Delete) endpoints for `Transcripts`, `Memos`, and `Codes`. | ✅          |

------



### 🧠 Phase 2: AI Processing Pipeline (✅ Completed)



| **TASK**                 | **DESCRIPTION**                                              | **STATUS** |
| ------------------------ | ------------------------------------------------------------ | ---------- |
| **On-Demand Processing** | Create a `/transcripts/process-ai` endpoint that reads a `Transcript`'s file, generates `Chunks` with embeddings, and saves them to the DB. | ✅          |
| **Status Tracking**      | Implement a `status` field (`new`, `processing`, `processed`) in the `Transcript` model to manage the AI processing state. | ✅          |
| **Configurable AI**      | Allow all AI service functions (`get_embedding`, `analyze_chunk`, etc.) to accept a user-defined `AIConfig` (API key, URL, models). | ✅          |
| **Default Configs**      | Create a `/config/defaults` endpoint to securely load default settings from the backend's `.env` file into the frontend UI. | ✅          |

------



### 🖥️ Phase 3: Frontend Interface (✅ Completed)



| **TASK**               | **DESCRIPTION**                                              | **STATUS** |
| ---------------------- | ------------------------------------------------------------ | ---------- |
| **Frontend Framework** | Build the user interface using **Streamlit**.                | ✅          |
| **Unified UI**         | Create a single-page, tabbed interface for "AI Analysis" and "Manual Management". | ✅          |
| **Upload Workflow**    | Implement a sidebar uploader that provides a "Process for AI" button based on the transcript's `status`. | ✅          |
| **Content Viewer**     | Implement "View Content" toggles in the "Manual Management" tab to load and display full `Transcript` and `Memo` content on demand. | ✅          |
| **Manual Coding**      | Create a sidebar form to manually add a new `Code`, allowing association with either a `Transcript` or a `Memo` from a dropdown. | ✅          |

------



### 🤖 Phase 4: Core AI Features (✅ Completed)



| **TASK**               | **DESCRIPTION**                                              | **STATUS** |
| ---------------------- | ------------------------------------------------------------ | ---------- |
| **AI-Generated Codes** | Implement a "Generate & Save AI Codes" button that analyzes all `Chunks` of a transcript and saves the results to the `Code` table. | ✅          |
| **AI-Generated Memos** | Implement a "Generate Memo Preview" button and a "Save Memo" workflow that saves the AI-generated memo to the `Memo` table. | ✅          |
| **Semantic Search**    | Implement a search bar that takes a user query, generates an embedding, and finds the most similar `Chunks` from the database. | ✅          |
| **Success Toasts**     | Use `st.toast` to provide non-blocking confirmation when AI content is successfully saved. | ✅          |

------



### 🧭 Phase 5: Next Steps (MVP+ Roadmap) (⏳ Pending)



| **TASK**               | **DESCRIPTION**                                              | **STATUS** |
| ---------------------- | ------------------------------------------------------------ | ---------- |
| **Interactive Coder**  | *[Next Feature]* Replace the manual text-box coding with an interactive UI where the user can highlight text directly from the "View Content" area to create a code. | ⏳          |
| **Codebook Manager**   | *[Next Feature]* Create a new UI tab (or page) to view, manage, and define all unique codes. This would allow merging duplicates and adding descriptions (this is what your "Categories" feature was likely aiming for). | ⏳          |
| **Export Function**    | Implement "Export to CSV/JSON" buttons to download all codes or memos associated with a transcript. | ⏳          |
| **Analysis Dashboard** | Implement basic visualizations (as you listed) like code frequency charts or co-occurrence heatmaps. | ⏳          |