from flask import Blueprint, jsonify, render_template, request
import os
from pyresparser import ResumeParser
import PyPDF2
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk

upload_resume_bp = Blueprint('upload_resume', __name__)
nltk.download('stopwords')

# Define professions and required skills mapping
PROFESSIONS = {
    "Software Developer": ["python", "java", "javascript", "c++", "web development", "git", "sql", "react", "node.js"],
    "Data Scientist": ["data science", "machine learning", "data analysis", "python", "r", "pandas", "numpy", "statistics"],
    "DevOps Engineer": ["devops", "cloud computing", "docker", "kubernetes", "aws", "terraform", "ci/cd", "linux"],
    "Project Manager": ["project management", "agile", "scrum", "leadership", "budgeting", "communication"],
    "Digital Marketer": ["digital marketing", "seo", "social media", "content marketing", "google analytics", "email marketing"],
    "Financial Analyst": ["finance", "accounting", "financial analysis", "excel", "valuation", "modeling"],
    "Human Resources Specialist": ["human resources", "recruitment", "employee relations", "onboarding", "screening"],
    "UI/UX Designer": ["ui/ux design", "user research", "wireframing", "prototyping", "figma", "sketch", "adobe xd"],
    "Cybersecurity Analyst": ["cybersecurity", "network security", "vulnerability assessment", "firewalls", "penetration testing"],
    "Data Engineer": ["data engineering", "etl", "sql", "big data", "spark", "hadoop", "data pipelines"]
}

def recommend_courses_dynamic(skills, num_courses=4):
    import sys
    if hasattr(sys, '_MEIPASS'):
        csv_path = os.path.join(sys._MEIPASS, "data/model_data/dataset/course_recommendation/preprocessed_data.csv")
    else:
        csv_path = "data/model_data/dataset/course_recommendation/preprocessed_data.csv"
    if not os.path.exists(csv_path):
        return []
    
    try:
        df = pd.read_csv(csv_path)
        if df.empty or "Description" not in df.columns:
            return []

        query = " ".join(skills)
        if not query.strip():
            # Return fallback head courses if query is empty
            return [{"title": row["Title"].title(), "category": "General Track"} for _, row in df.head(num_courses).iterrows()]
        
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(df['Description'].fillna(''))
        
        query_vector = vectorizer.transform([query])
        similarity_scores = cosine_similarity(query_vector, tfidf_matrix).flatten()
        
        top_indices = similarity_scores.argsort()[::-1][:num_courses]
        
        recommendations = []
        for idx in top_indices:
            row = df.iloc[idx]
            recommendations.append({
                "title": str(row["Title"]).title(),
                "category": "Recommended Match"
            })
        return recommendations
    except Exception as e:
        print(f"Error recommending courses: {e}")
        return []

@upload_resume_bp.route("/upload-resume", methods=["POST"])
def upload_resume():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.pdf'):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    # Ensure uploads directory exists
    uploads_dir = os.path.join(os.getcwd(), "uploads")
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)

    path = os.path.join(uploads_dir, filename)
    file.save(path)

    try:
        # 1. Parse resume details using pyresparser
        data = ResumeParser(path).get_extracted_data()
        if not data:
            data = {}

        # 2. Read PDF text using PyPDF2 for checklist check
        pdf_text = ""
        with open(path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    pdf_text += page_text

        # 3. Calculate structure checklist & ATS score (100-point scale)
        checklist = {
            "Objective / Summary": any(kw in pdf_text for kw in ["Objective", "Summary", "OBJECTIVE", "SUMMARY"]),
            "Education": any(kw in pdf_text for kw in ["Education", "School", "College", "EDUCATION"]),
            "Experience": any(kw in pdf_text for kw in ["EXPERIENCE", "Experience", "Work Experience", "WORK EXPERIENCE"]),
            "Internships": any(kw in pdf_text for kw in ["INTERNSHIPS", "INTERNSHIP", "Internships", "Internship"]),
            "Skills": any(kw in pdf_text for kw in ["SKILLS", "SKILL", "Skills", "Skill"]),
            "Hobbies / Interests": any(kw in pdf_text for kw in ["HOBBIES", "Hobbies", "Interest", "Interests", "INTERESTS"]),
            "Achievements": any(kw in pdf_text for kw in ["ACHIEVEMENTS", "Achievements"]),
            "Certifications": any(kw in pdf_text for kw in ["CERTIFICATIONS", "Certifications", "Certification"]),
            "Projects": any(kw in pdf_text for kw in ["PROJECTS", "PROJECT", "Projects", "Project"])
        }

        score = 0
        if checklist["Objective / Summary"]: score += 6
        if checklist["Education"]: score += 12
        if checklist["Experience"]: score += 16
        if checklist["Internships"]: score += 6
        if checklist["Skills"]: score += 7
        if checklist["Hobbies / Interests"]: score += 9
        if checklist["Achievements"]: score += 13
        if checklist["Certifications"]: score += 12
        if checklist["Projects"]: score += 19

        # 4. Classify profession domain based on skill match
        matched_skills = data.get("skills") or []
        skills_lower = [s.lower() for s in matched_skills]
        
        classified_domain = "Software Developer" # default
        max_matches = 0
        
        for domain, required in PROFESSIONS.items():
            matches = len(set(skills_lower) & set(required))
            if matches > max_matches:
                max_matches = matches
                classified_domain = domain

        # 5. Get recommended missing skills
        domain_skills = PROFESSIONS.get(classified_domain, [])
        missing_skills = [s.title() for s in domain_skills if s.lower() not in skills_lower]

        # 6. Recommend courses based on domain and skills
        courses = recommend_courses_dynamic(skills_lower + [classified_domain], 4)

        # Build analysis report
        analysis = {
            "profile": {
                "name": data.get("name") or "",
                "email": data.get("email") or "",
                "mobile": data.get("mobile_number") or "",
                "college": data.get("college_name") or "",
                "degree": data.get("degree") or ""
            },
            "classified_domain": classified_domain,
            "score": score,
            "checklist": checklist,
            "skills": {
                "matched": [s.title() for s in matched_skills],
                "recommended": missing_skills
            },
            "courses": courses
        }

        return jsonify({"analysis": analysis})
    except Exception as e:
        print(f"Error parsing resume PDF: {e}")
        return jsonify({"error": f"Failed to parse resume: {str(e)}"}), 500
