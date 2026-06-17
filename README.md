# AI STORYBOOK

*Interactive Educational Platform with Generative AI Integration*

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?style=flat&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=flat&logo=tailwind-css&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=flat&logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white)

## Project Overview
**AI Storybook** is an innovative, full-stack Learning Management System (LMS) designed to transform static educational materials into highly interactive, AI-generated storybooks. By leveraging Large Language Models (LLMs) and advanced media processing, the platform automates the creation of segmented narratives, dynamic illustrations, and natural text-to-speech audio, providing an immersive learning experience for students and streamlined classroom management for educators.

---

## Core Architecture & Technical Highlights

* ⚙️ **Asynchronous AI Processing:** Implemented a robust background task queue using **Celery** and **Redis** to handle heavy AI generation (Text, Image, TTS) and PDF extraction concurrently, preventing application bottlenecks and ensuring high availability.
* 🧠 **Generative AI Integration:** Engineered complex prompt pipelines utilizing **Google Gemini API** (Gemini Pro, Flash Image, TTS) with strict safety filter fallbacks and dynamic prompt sanitization to guarantee safe, highly consistent character designs across generated scenes.
* ☁️ **Scalable Backend & Cloud Storage:** Built a monolithic architecture with **Django** and **PostgreSQL**, integrated with **Supabase S3** for efficient, chunk-managed media storage (handling generated audio and high-resolution images).
* 💻 **Interactive Frontend:** Developed a responsive, user-friendly interface using **Tailwind CSS** and JavaScript, featuring a dynamic Flipbook reader with synchronized audio playback and real-time automated post-tests.

---

## Key Features

* 🏫 **Classroom Management:** Secure authentication (Google OAuth/Allauth), role-based access control (Teachers/Students), and seamless classroom enrollment.
* 🪄 **Automated Content Creation:** One-click conversion of lesson plans into 20-scene storybooks complete with AI-generated visual consistency and automated multiple-choice assessments.
* 📊 **Engagement & Analytics:** Real-time grading, student interaction tracking (likes, shares, favorites), and comprehensive reporting dashboards for administrators.

---

## Tech Stack

| Category | Technologies |
| :--- | :--- |
| 🐍 **Backend** | Python 3.12, Django 5.2, PostgreSQL |
| 🚀 **Infrastructure & Queues** | Celery, Redis |
| 🤖 **AI & APIs** | Google Gemini API (Multimodal), Supabase Storage |
| 🎨 **Frontend** | HTML5, JavaScript, Tailwind CSS |
| 🎬 **Media Processing** | FFMPEG, Pydub, PyPDF2 |
