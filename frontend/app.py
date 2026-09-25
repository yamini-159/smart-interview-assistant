import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from audio_recorder_streamlit import audio_recorder
from speech_handler import transcribe_audio_bytes

st.set_page_config(page_title="Smart Interview Assistant", page_icon="🤖", layout="wide")

st.title("🤖 Smart AI Interview Preparation Assistant")
st.caption("Perfect your technical, aptitude, and resume rounds with real-time AI feedback.")
st.markdown("---")

menu = ["🏠 Home / Practice", "📄 Resume Interview", "📊 History & Analytics"]
choice = st.sidebar.selectbox("Navigate Project Panels", menu)

BACKEND_URL = str("https://smart-interview-assistant-4t15.onrender.com").strip().replace("\xa0", "")

# --- 🏠 PANEL 1: STANDARD PRACTICE ---
if choice == "🏠 Home / Practice":
    st.subheader("🎯 Custom Practice Session")
    
    col1, col2 = st.columns(2)
    with col1:
        job_role = st.text_input("Target Job Role", value="AIML Engineer")
    with col2:
        round_type = st.selectbox("Interview Round Type", ["Technical", "HR", "Aptitude"])
        
    if st.button("Generate Interview Questions 🚀", type="primary"):
        with st.spinner("AI is crafting your questions..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/generate-questions",
                    json={"job_role": job_role, "round_type": round_type}
                )
                if response.status_code == 200:
                    st.session_state["practice_data"] = response.json()
                    st.success("Session loaded successfully!")
                else:
                    st.error("Backend error generating details.")
            except Exception as e:
                st.error(f"Connection lost to server: {e}")

    if "practice_data" in st.session_state:
        data = st.session_state["practice_data"]
        
        # Aptitude Round
        if data.get("is_mcq"):
            st.info("📝 **Aptitude Mode Active:** Select the correct options below.")
            score = 0
            questions_list = data["questions"]
            user_answers = {}
            
            for idx, q in enumerate(questions_list):
                st.write(f"**Q{idx+1}: {q['question']}**")
                user_answers[idx] = st.radio(f"Select answer for Q{idx+1}:", q["options"], key=f"mcq_{idx}")
            
            if st.button("Submit Aptitude Answers ✅"):
                for idx, q in enumerate(questions_list):
                    if user_answers[idx] == q["correct_answer"]:
                        score += 1
                        st.success(f"✔️ Q{idx+1} Correct!")
                    else:
                        st.error(f"❌ Q{idx+1} Incorrect! Correct: {q['correct_answer']}")
                
                final_score = int((score / len(questions_list)) * 10)
                st.metric(label="Overall Score", value=f"{final_score}/10")
                
                requests.post(f"{BACKEND_URL}/save-history", json={
                    "round_type": "Aptitude",
                    "question": "Aptitude Test Session Set",
                    "user_answer": "Submitted answers via MCQ",
                    "score": final_score,
                    "feedback": f"Answered {score}/{len(questions_list)} correctly."
                })
        
        # Standard Technical / HR Round
        else:
            st.info("💡 Answer each question below using Voice or Text to get individual evaluation.")
            q_list = data["questions"] if isinstance(data["questions"], list) else [data["questions"]]
            
            for idx, q_text in enumerate(q_list, 1):
                st.markdown(f"### ❓ Question {idx}")
                st.info(f"**{q_text}**")
                
                widget_key = f"text_prac_ans_{idx}"
                if widget_key not in st.session_state:
                    st.session_state[widget_key] = ""

                input_col1, input_col2 = st.columns([1, 1])

                with input_col1:
                    st.markdown("**🎙️ Record Answer**")
                    st.caption("Click mic icon to Start/Stop recording")
                    audio_bytes = audio_recorder(
                        text="",
                        recording_color="#e8b62c",
                        neutral_color="#6aa36f",
                        icon_size="2x",
                        key=f"audio_prac_{idx}"
                    )
                    
                    if audio_bytes:
                        with st.spinner("Transcribing audio..."):
                            transcribed_text = transcribe_audio_bytes(audio_bytes)
                            if not transcribed_text.startswith("ERROR"):
                                st.session_state[widget_key] = transcribed_text
                                st.success("Transcribed!")
                            else:
                                st.error(transcribed_text)

                with input_col2:
                    st.markdown("**✍️ Type / Edit Answer**")
                    ans = st.text_area(
                        f"Your Answer for Q{idx}:", 
                        key=widget_key, 
                        height=120
                    )
                
                if st.button(f"Evaluate Q{idx} 📈", key=f"btn_eval_prac_{idx}"):
                    final_ans = st.session_state[widget_key]
                    if not final_ans.strip():
                        st.warning("Please record or type an answer first!")
                    else:
                        with st.spinner("AI evaluating answer..."):
                            res = requests.post(f"{BACKEND_URL}/evaluate-answer", json={
                                "question": q_text,
                                "user_answer": final_ans
                            })
                            if res.status_code == 200:
                                ev = res.json()
                                st.success(f"Score: **{ev['score']}/10**")
                                st.write(f"🌟 **Strengths:** {ev['strengths']}")
                                st.write(f"⚠️ **Improvement:** {ev['weaknesses']}")
                                with st.expander("💡 Model Expert Answer"):
                                    st.write(ev['model_answer'])
                                
                                requests.post(f"{BACKEND_URL}/save-history", json={
                                    "round_type": data["round_type"],
                                    "question": q_text,
                                    "user_answer": final_ans,
                                    "score": ev['score'],
                                    "feedback": f"Strengths: {ev['strengths']} | Weaknesses: {ev['weaknesses']}"
                                })

# --- 📄 PANEL 2: RESUME INTERVIEW ---
elif choice == "📄 Resume Interview":
    st.subheader("📁 Custom Profile Resume Interview")
    st.markdown("Upload your placement PDF resume to extract personalized project questions.")
    
    r_type = st.selectbox("Interview Focus Round", ["Technical", "HR"])
    uploaded_file = st.file_uploader("Choose your Resume PDF", type=["pdf"])
    
    if uploaded_file is not None and st.button("Extract Data & Challenge Me 🚀"):
        with st.spinner("Analyzing resume content with Gemini AI..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                data_form = {"round_type": r_type}
                res = requests.post(f"{BACKEND_URL}/generate-questions-from-resume", files=files, data=data_form)
                
                if res.status_code == 200:
                    st.session_state["resume_data"] = res.json()
                    st.success("Resume questions generated! Review below.")
                else:
                    st.error("Backend failed processing PDF.")
            except Exception as e:
                st.error(f"Error handling profile submission: {e}")

    if "resume_data" in st.session_state:
        st.write("---")
        st.subheader("🎯 Project & Experience Questions")
        res_qs = st.session_state["resume_data"].get("questions", [])
        
        if isinstance(res_qs, str):
            res_qs = [res_qs]

        for idx, q_text in enumerate(res_qs, 1):
            st.markdown(f"### 🎯 Resume Question {idx}")
            st.info(f"**{q_text}**")
            
            res_widget_key = f"text_res_ans_{idx}"
            if res_widget_key not in st.session_state:
                st.session_state[res_widget_key] = ""

            r_col1, r_col2 = st.columns([1, 1])

            with r_col1:
                st.markdown("**🎙️ Record Answer**")
                st.caption("Click mic icon to Start/Stop recording")
                audio_bytes_res = audio_recorder(
                    text="",
                    recording_color="#e8b62c",
                    neutral_color="#6aa36f",
                    icon_size="2x",
                    key=f"audio_res_{idx}"
                )
                
                if audio_bytes_res:
                    with st.spinner("Transcribing audio..."):
                        transcribed_text = transcribe_audio_bytes(audio_bytes_res)
                        if not transcribed_text.startswith("ERROR"):
                            st.session_state[res_widget_key] = transcribed_text
                            st.success("Transcribed!")
                        else:
                            st.error(transcribed_text)

            with r_col2:
                st.markdown("**✍️ Type / Edit Answer**")
                user_ans = st.text_area(
                    f"Your Answer for Resume Q{idx}:", 
                    key=res_widget_key, 
                    height=120
                )
            
            if st.button(f"Submit Answer for Resume Q{idx}", key=f"btn_res_{idx}"):
                final_res_ans = st.session_state[res_widget_key]
                if not final_res_ans.strip():
                    st.warning("Please record or type an answer first!")
                else:
                    with st.spinner("AI evaluating answer..."):
                        eval_res = requests.post(f"{BACKEND_URL}/evaluate-answer", json={
                            "question": q_text,
                            "user_answer": final_res_ans
                        })
                        if eval_res.status_code == 200:
                            ev = eval_res.json()
                            st.success(f"Score: **{ev['score']}/10**")
                            st.write(f"🌟 **Strengths:** {ev['strengths']}")
                            st.write(f"⚠️ **Improvement:** {ev['weaknesses']}")
                            with st.expander("💡 Ideal Model Answer"):
                                st.write(ev['model_answer'])
                                
                            requests.post(f"{BACKEND_URL}/save-history", json={
                                "round_type": f"Resume ({r_type})",
                                "question": q_text,
                                "user_answer": final_res_ans,
                                "score": ev['score'],
                                "feedback": f"Strengths: {ev['strengths']} | Weaknesses: {ev['weaknesses']}"
                            })

# --- 📊 PANEL 3: HISTORY & ANALYTICS DASHBOARD ---
elif choice == "📊 History & Analytics":
    st.subheader("📈 Performance Analytics & Progress Dashboard")
    st.caption("Track your historical mock interview scores and domain strengths over time.")
    
    # PDF Export Section
    if st.button("📄 Export PDF Summary Report"):
        with st.spinner("Generating PDF report..."):
            pdf_res = requests.get(f"{BACKEND_URL}/export-pdf")
            if pdf_res.status_code == 200:
                st.download_button(
                    label="💾 Click to Download PDF",
                    data=pdf_res.content,
                    file_name="Smart_AI_Interview_Report.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("Failed to generate PDF report from backend.")

    st.markdown("---")

    try:
        res = requests.get(f"{BACKEND_URL}/get-history")
        if res.status_code == 200:
            history_data = res.json().get("history", [])
            
            if not history_data:
                st.info("No recorded interview attempts yet. Complete a practice round to see analytics!")
            else:
                df = pd.DataFrame(history_data)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0)

                # --- 1. Top KPI Metrics ---
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Questions", len(df))
                with col2:
                    st.metric("Average Score", f"{df['score'].mean():.1f} / 10")
                with col3:
                    st.metric("Highest Score", f"{int(df['score'].max())} / 10")
                with col4:
                    st.metric("Latest Score", f"{int(df['score'].iloc[0])} / 10")

                st.markdown("---")

                # --- 2. Plotly Score Trends Line Chart ---
                st.markdown("### 📊 Performance Trend Over Time")
                df_sorted = df.sort_values("timestamp")
                fig_trend = px.line(
                    df_sorted,
                    x="timestamp",
                    y="score",
                    color="round_type",
                    markers=True,
                    title="Score Progression Across Interview Attempts",
                    labels={"timestamp": "Date & Time", "score": "Score (0-10)", "round_type": "Round Type"},
                    range_y=[0, 10]
                )
                fig_trend.update_layout(template="plotly_white", height=380)
                st.plotly_chart(fig_trend, width='stretch')

                # --- 3. Plotly Skill/Round Breakdown Radar & Bar Chart ---
                chart_col1, chart_col2 = st.columns([1, 1])

                with chart_col1:
                    st.markdown("### 🎯 Score Breakdown by Round Type")
                    avg_by_round = df.groupby("round_type")["score"].mean().reset_index()
                    fig_bar = px.bar(
                        avg_by_round,
                        x="round_type",
                        y="score",
                        color="round_type",
                        text_auto=".1f",
                        range_y=[0, 10],
                        labels={"score": "Avg Score", "round_type": "Round Type"}
                    )
                    fig_bar.update_layout(showlegend=False, template="plotly_white", height=350)
                    st.plotly_chart(fig_bar, width='stretch')

                with chart_col2:
                    st.markdown("### 🕸️ Skill Competency Radar")
                    categories = avg_by_round['round_type'].tolist()
                    scores = avg_by_round['score'].tolist()

                    fig_radar = go.Figure(data=go.Scatterpolar(
                        r=scores + [scores[0]],  # Close radar loop
                        theta=categories + [categories[0]],
                        fill='toself',
                        name='Average Score'
                    ))
                    fig_radar.update_layout(
                        polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
                        showlegend=False,
                        template="plotly_white",
                        height=350
                    )
                    st.plotly_chart(fig_radar, width='stretch')

                # --- 4. Detailed History Table ---
                with st.expander("📄 View Detailed Interview History Logs"):
                    for entry in history_data:
                        st.write(f"**[{entry['timestamp']}] {entry['round_type']}** — Score: **{entry['score']}/10**")
                        st.write(f"**Q:** {entry['question']}")
                        st.write(f"**A:** {entry['user_answer']}")
                        st.caption(f"Feedback: {entry['feedback']}")
                        st.markdown("---")

    except Exception as e:
        st.error(f"Error loading analytics dashboard: {e}")