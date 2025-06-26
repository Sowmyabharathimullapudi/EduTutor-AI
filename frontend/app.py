mport streamlit as st
import pyrebase
import requests
import virtualassistant
from datetime import datetime
import re
st.set_page_config(page_title="EduTutor AI", layout="wide")
# Firebase config
firebaseConfig = {
}
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
db = firebase.database()

# --------------- Session State ----------------
if "is_logged_in" not in st.session_state:
    st.session_state["is_logged_in"] = False
if "user" not in st.session_state:
    st.session_state["user"] = None
if "role" not in st.session_state:
    st.session_state["role"] = ""
if "name" not in st.session_state:
    st.session_state["name"] = ""
# -------------------- UI --------------------
st.title("📘 EduTutor AI")

if not st.session_state["is_logged_in"]:
    menu = st.sidebar.selectbox("Menu", ["Login", "Signup"])
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")

    # ---------- SIGNUP ----------
    if menu == "Signup":
        role = st.sidebar.selectbox("I am a", ["Student", "Teacher"])
        name = st.sidebar.text_input("Your Name")
        if st.sidebar.button("Create Account"):
            try:
                user = auth.create_user_with_email_and_password(email, password)
                uid = user['localId']

                db.child("users").child(uid).set({
                    "email": email,
                    "role": role,
                    "name": name
                })
                st.success("✅ Account created successfully! Please log in.")
            except Exception as e:
                st.error(f"❌ Signup failed: {e}")

    # ---------- LOGIN ----------
    elif menu == "Login":
        if st.sidebar.button("Login"):
            try:
                user = auth.sign_in_with_email_and_password(email, password)
                uid = user["localId"]

                # Check if user details exist in DB
                user_data = db.child("users").child(uid).get().val()

                if user_data and "role" in user_data and "name" in user_data:
                    st.session_state["user"] = user
                    st.session_state["role"] = user_data["role"]
                    st.session_state["name"] = user_data["name"]
                    st.session_state["is_logged_in"] = True

                    st.success(f"✅ Login successful! Logged in as {user_data['role']}.")
                    st.rerun()  # 🔁 Force Streamlit to refresh UI
                else:
                    st.error("❌ Login failed: Your account is not fully registered. Please sign up first.")
            except Exception as e:
                st.error(f"❌ Login failed: {e}")

# ---------- DASHBOARD ----------
else:
    # Default page setup
    if "page" not in st.session_state:
        st.session_state["page"] = "Dashboard"

    # Sidebar navigation
    st.sidebar.success(f"👋 Welcome {st.session_state['name']}!")
    st.sidebar.write(f"Role: **{st.session_state['role']}**")

    # Sidebar menu options
    if st.sidebar.button("🏠 Dashboard"):
        st.session_state["page"] = "Dashboard"
    if st.sidebar.button("🤖 Virtual Assistant"):
        st.session_state["page"] = "Virtual Assistant"
    if st.sidebar.button("📝 Quiz Generator"):
        st.session_state["page"] = "Quiz Generator"
    if st.sidebar.button("📊 Student History"):
        st.session_state["page"] = "Student History"
    if st.sidebar.button("📜 Chat History"):
        st.session_state["page"] = "Chat History"
    if st.sidebar.button("💡 AI Summarizer"):
        st.session_state["page"] = "AI Summarizer"
    if st.sidebar.button("🧠 AI Flashcards"):
        st.session_state["page"] ="AI Flashcards"
    if st.sidebar.button("🚪 Logout"):
        st.session_state["is_logged_in"] = False
        st.session_state["user"] = None
        st.session_state["role"] = ""
        st.session_state["name"] = ""
        st.session_state["page"] = "Dashboard"
        st.rerun()
    # ---------------- Main Content ----------------
    if st.session_state["page"] == "Dashboard":
        st.header("📘 Dashboard")
        if st.session_state["role"] == "Student":
            st.success("🎓 You are logged in as a student.")
        elif st.session_state["role"] == "Teacher":
            st.success("📚 You are logged in as a teacher.")
    elif st.session_state["page"] == "Virtual Assistant":
        st.header("🤖 EduTutor AI - Virtual Assistant")
        st.write("Ask your study-related questions here...")
        user_input = st.text_area("💬 Ask a question:")
        if st.button("Get Answer") and user_input.strip():
            with st.spinner("Thinking..."):
                response = virtualassistant.ask_tutor(user_input)
            st.success("✅ Answer")
            st.write(response)
            # 🔽 Save chat to backend
            import requests
            def save_chat_to_backend(uid, question, answer):
                url = "http://localhost:8000/save-chat-history"
                payload = {"uid": uid, "question": question, "answer": answer}
                try:
                    requests.post(url, json=payload)
                except Exception as e:
                    st.warning(f"⚠️ Couldn't save chat: {e}")

            if "user" in st.session_state and st.session_state["user"]:
                uid = st.session_state["user"]["localId"]
                save_chat_to_backend(uid, user_input, response)
# Only run this block for the Quiz Generator page
    elif st.session_state["page"] == "Quiz Generator":
        st.title("🧠 Edu Tutor AI -  Quiz Generator")
        st.markdown("Generate a 10-question quiz based on your topic and difficulty level.")
        # Inputs
        uid = st.session_state["user"]["localId"]
        topic = st.text_input("Enter quiz topic", "Recursion")
        difficulty = st.selectbox("Select difficulty", ["easy", "medium", "hard"])
        # Session state
        if "quiz" not in st.session_state:
            st.session_state.quiz = []
        if "submitted" not in st.session_state:
            st.session_state.submitted = False
        if "user_answers" not in st.session_state:
            st.session_state.user_answers = {}
        # Generate Quiz
        if st.button("🎯 Generate Quiz"):
            if not uid or not topic:
                st.warning("Please provide both UID and Topic.")
            else:
                with st.spinner("Generating quiz... please wait"):
                    try:
                        response = requests.post(
                            "http://localhost:8000/generate-quiz",
                            json={"uid": uid, "topic": topic, "difficulty": difficulty}
                        )
                        if response.status_code == 200:
                            quiz = response.json()
                            if len(quiz) == 10:
                                st.session_state.quiz = quiz
                                st.session_state.user_answers = {}
                                st.session_state.submitted = False
                                st.success("✅ Quiz generated successfully!")
                            else:
                                st.error("Quiz must contain exactly 10 questions. Try again.")
                        else:
                            st.error(f"Failed to generate quiz: {response.json()['detail']}")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        # Quiz UI
        if st.session_state.quiz and not st.session_state.submitted:
            st.subheader("📝 Attempt the Quiz")
            for i, q in enumerate(st.session_state.quiz):
                options_display = [f"{key}. {val}" for key, val in q["options"].items()]
                selected = st.radio(
                    label=f"**Q{i+1}. {q['question']}**",
                    options=options_display,
                    key=f"user_q{i}"
                )
                if selected:
                    st.session_state.user_answers[i] = selected[0]

            if st.button("✅ Submit Quiz"):
                if len(st.session_state.user_answers) < 10:
                    st.warning("Please answer all questions before submitting.")
                else:
                    st.session_state.submitted = True
                    # Calculate result and prepare data
                    correct = 0
                    quiz_result = []
                    for i, q in enumerate(st.session_state.quiz):
                        user_ans = st.session_state.user_answers.get(i)
                        correct_ans = q["answer"]
                        if user_ans == correct_ans:
                            correct += 1
                        quiz_result.append({
                            "question": q["question"],
                            "options": q["options"],
                            "answer": correct_ans,
                            "user_answer": user_ans
                        })
                    timestamp = datetime.now().isoformat()
                    history_payload = {
                        "uid": uid,
                        "topic": topic,
                        "difficulty": difficulty,
                        "score": correct,
                        "total": 10,
                        "timestamp": timestamp,
                        "quiz": quiz_result
                    }
                    try:
                        save_resp = requests.post(
                            "http://localhost:8000/save-quiz-history",
                            json=history_payload
                        )
                        if save_resp.status_code == 200:
                            st.success("📚 Quiz history saved successfully!")
                        else:
                            st.error("❌ Failed to save quiz history.")
                    except Exception as e:
                        st.error(f"Error saving quiz history: {str(e)}")
        # Show results
        if st.session_state.quiz and st.session_state.submitted:
            st.subheader("📊 Quiz Results")
            correct = 0
            for i, q in enumerate(st.session_state.quiz):
                correct_ans = q["answer"]
                selected = st.session_state.user_answers.get(i, "")
                is_correct = (selected == correct_ans)
                st.markdown(f"**Q{i+1}. {q['question']}**")
                for opt_key, opt_val in q["options"].items():
                    label = f"{opt_key}. {opt_val}"
                    if opt_key == correct_ans and opt_key == selected:
                        st.success(f"✅ {label} (Correct Answer & You Selected)")
                    elif opt_key == correct_ans:
                        st.info(f"✔️ {label} (Correct Answer)")
                    elif opt_key == selected:
                        st.error(f"❌ {label} (Your Answer)")
                    else:
                        st.write(label)
                st.markdown("---")
                if is_correct:
                    correct += 1
            st.info(f"🏁 You scored **{correct} out of 10**.")

    elif st.session_state["page"] == "Student History" :
        st.header("📊  student Quiz History")
        st.write("Here is your performance summary.")
        import streamlit as st
        import requests
        from datetime import datetime
        st.title("📘 Your Quiz History")
        uid = st.session_state["user"]["localId"]
        try:
            with st.spinner("Fetching quiz history..."):
                res = requests.get(f"http://localhost:8000/student-history?uid={uid}")
                if res.status_code == 200:
                    history = res.json()
                    if not history:
                        st.info("No quiz history found. Try taking a quiz first!")
                    else:
                        for idx, record in enumerate(history[::-1]):
                            with st.expander(f"📅 {record['timestamp']} | {record['topic']} | {record['difficulty']} | Score: {record['score']}/10"):
                                for i, q in enumerate(record["quiz"]):
                                    st.markdown(f"**Q{i+1}. {q['question']}**")
                                    for opt_key, opt_val in q["options"].items():
                                        label = f"{opt_key}. {opt_val}"
                                        if opt_key == q["answer"] and opt_key == q["user_answer"]:
                                            st.success(f"✅ {label} (Correct Answer & You Selected)")
                                        elif opt_key == q["answer"]:
                                            st.info(f"✔️ {label} (Correct Answer)")
                                        elif opt_key == q["user_answer"]:
                                            st.error(f"❌ {label} (Your Answer)")
                                        else:
                                            st.write(label)
                                    st.markdown("---")
                else:
                    st.error("❌ Failed to load quiz history.")
        except Exception as e:
            st.error(f"Error: {str(e)}")
    elif st.session_state["page"] == "Chat History":
        st.header("📜 Your Chat History")
        with st.spinner("Loading Previous chat... please wait"):
            try:
                import requests
                uid = st.session_state["user"]["localId"]
                res = requests.get(f"http://localhost:8000/get-chat-history/{uid}")
                if res.status_code == 200:
                        response = requests.get(f"http://localhost:8000/get-chat-history/{uid}")
                        if response.status_code == 200:
                            data = response.json()
                            if data:
                                for i, chat in enumerate(data.values()):
                                    st.write(f"**Q{i+1}:** {chat['question']}")
                                    st.write(f"**A{i+1}:** {chat['answer']}")
                            else:
                                st.info("No chat history found.")

                        else:
                                    st.info("No chat history found.")
                else:
                    st.error("Failed to load chat history.")
            except Exception as e:
                st.error(f"⚠️ Error fetching chat history: {e}")
    elif st.session_state["page"] == "AI Summarizer":
        API_BASE = "http://localhost:8000"  # Change if deployed
        st.header("🤖 EduTutor AI - AI Summarizer")
        st.write("Paste your notes below and get a concise 5-point summary!")
        user_notes = st.text_area("✍️ Enter your study notes here")
        if st.button("Summarize"):
                if not user_notes.strip():
                    st.warning("Please enter some text to summarize.")
                else:
                    with st.spinner("Generating summary..."):
                        try:
                            response = requests.post(
                                f"http://localhost:8000/summarize-notes",
                                json={"notes": user_notes}
                            )
                            if response.status_code == 200:
                                raw_summary = response.json()["summary"]
                                # 🧹 Clean and standardize the summary
                                import re
                                raw_lines = re.findall(r'\d+\.\s+.*?(?=\n\d+\.|\Z)', raw_summary.strip(), re.DOTALL)
                                seen = set()
                                cleaned = []
                                for line in raw_lines:
                                    sentence = re.sub(r'\s+', ' ', line.strip())  # normalize whitespace
                                    if sentence not in seen and len(sentence.split()) > 3:
                                        cleaned.append(sentence)
                                        seen.add(sentence)
                                # ✅ Display final cleaned summary (max 7 points)
                                st.success("Here’s your summary:")
                                for i, point in enumerate(cleaned[:7], start=1):
                                    # Remove previous numbering and reformat
                                    content = re.sub(r'^\d+\.\s*', '', point)
                                    st.markdown(f"✅👉 **{i}. {content}**")
                            else:
                                st.error(f"Error: {response.text}")
                        except Exception as e:
                            st.error(f"Request failed: {e}")
    elif st.session_state["page"] == "AI Flashcards":
        st.header("🧠 EduTutor AI - Flashcard Generator")
        st.write("Turn your study notes into interactive flashcards!")
        API_BASE = "http://localhost:8000"
        user_notes = st.text_area("📚 Paste your study notes here")
        if st.button("Generate Flashcards"):
            if not user_notes.strip():
                st.warning("Please enter some notes.")
            else:
                with st.spinner("Generating flashcards..."):
                    try:
                        response = requests.post(
                            f"{API_BASE}/generate-flashcards",
                            json={"notes": user_notes}
                        )
                        if response.status_code == 200:
                            flashcards_raw = response.json()["flashcards"]
                            # Extract Q&A pairs
                            pairs = re.findall(r"Q:\s*(.*?)\nA:\s*(.*?)(?=\nQ:|\Z)", flashcards_raw, re.DOTALL)
                            st.success("Here are your flashcards:")
                            for i, (q, a) in enumerate(pairs, 1):
                                with st.expander(f"Flashcard {i}: {q.strip()}"):
                                    st.write(f"**Answer:** {a.strip()}")
                        else:
                            st.error(f"Error: {response.text}")
                    except Exception as e:
                        st.error(f"Request failed: {e}")
