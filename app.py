import cv2
import requests
from bs4 import BeautifulSoup
import random
import re
from flask import Flask, render_template, request, jsonify
import time
import threading
import math
from flask import session, redirect, url_for, flash
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_pymongo import PyMongo
import random
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
import speech_recognition as sr

app = Flask(__name__)

# Load Haar Cascade classifiers for face and eye detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

# Global variables for time and tracking
start_time = 0
end_time = 0
eye_tracking_active = False
eye_movement_count = 0  # To store the number of detected eye movements
last_title = ""
last_word_count = 0
last_paragraph = ""
random_url = ""
correct_category = ""
user_id = ""
paragraph_aloud = ""

def scrape_wikipedia_paragraph(url, min_word_count=100):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1').get_text(strip=True)
        paragraphs = soup.find_all('p')

        for para in paragraphs:
            paragraph_text = para.get_text(strip=True)
            cleaned_paragraph = re.sub(r'\[\d+\]', ' ', paragraph_text)
            word_count = len(cleaned_paragraph.split())

            if word_count >= min_word_count:
                return title, cleaned_paragraph, word_count

        return title, "No paragraph with 100 words found.", 0
    else:
        return None, "Failed to retrieve the webpage.", 0

# List of Wikipedia URLs
wikipedia_urls = [
    'https://en.wikipedia.org/wiki/Taj_Mahal',
    'https://en.wikipedia.org/wiki/Eiffel_Tower',
    'https://en.wikipedia.org/wiki/Machu_Picchu',
    'https://en.wikipedia.org/wiki/Neuschwanstein_Castle',
    'https://en.wikipedia.org/wiki/Earth',
    'https://en.wikipedia.org/wiki/Saturn',
    'https://en.wikipedia.org/wiki/Victoria_Falls',
    'https://en.wikipedia.org/wiki/Great_Barrier_Reef',
    'https://en.wikipedia.org/wiki/Amazon_rainforest',
    'https://en.wikipedia.org/wiki/Artificial_intelligence',
    'https://en.wikipedia.org/wiki/Smartphone',
    'https://en.wikipedia.org/wiki/Internet'
]
categories = {
        "Historical Sites": [
            'https://en.wikipedia.org/wiki/Taj_Mahal',
            'https://en.wikipedia.org/wiki/Machu_Picchu',
            'https://en.wikipedia.org/wiki/Eiffel_Tower',
            'https://en.wikipedia.org/wiki/Neuschwanstein_Castle'
        ],
        "Planets": [
            'https://en.wikipedia.org/wiki/Earth',
            'https://en.wikipedia.org/wiki/Saturn'
        ],
        "Natural Wonders": [
            'https://en.wikipedia.org/wiki/Victoria_Falls',
            'https://en.wikipedia.org/wiki/Great_Barrier_Reef',
            'https://en.wikipedia.org/wiki/Amazon_rainforest'
        ],
        "Technology": [
            'https://en.wikipedia.org/wiki/Artificial_intelligence',
            'https://en.wikipedia.org/wiki/Smartphone',
            'https://en.wikipedia.org/wiki/Internet'
        ]
    }

app.secret_key = 'secret_key'  # Change this to a random secret key
app.config["MONGO_URI"] = "mongodb://localhost:27017/user_db"
mongo = PyMongo(app)

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    global user_id
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        pin = request.form.get('pin')

        user = mongo.db.users.find_one({'user_id': user_id})
        if user:
            if user['pin'] == pin:  # Check if the PIN matches
                #flash('Login successful!', 'success')
                return redirect(url_for('index'))  # Redirect to options.html
            else:
                flash('Invalid PIN!', 'danger')
        else:
            flash('User ID not found! Please register.', 'warning')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        user_id = request.form.get('user_id')
        pin = request.form.get('pin')
        state = request.form.get('state')
        age = request.form.get('age')

        mongo.db.users.insert_one({
            'name': name,
            'user_id': user_id,
            'pin': pin,
            'state': state,
            'age': age
        })
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        admin_user_id = request.form.get('admin_user_id')
        admin_password = request.form.get('admin_password')

        if admin_user_id == 'admin' and admin_password == 'admin':  # Hardcoded admin credentials
            #flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))  # Redirect to the admin dashboard
        else:
            flash('Invalid admin credentials!', 'danger')

    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    # Retrieve all users and their quiz results from the database
    users = mongo.db.users.find()

    # Pass user data to the template
    return render_template('admin_dashboard.html', users=users)


@app.route('/logout')
def logout():
    # Clear the session or any user-related data here
    session.clear()  # Clears all session data
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/start_timer', methods=['POST'])
def start_timer():
    global start_time, eye_tracking_active, eye_movement_count, last_title, last_word_count, last_paragraph, correct_category
    start_time = time.time()
    eye_tracking_active = True
    eye_movement_count = 0

    # Start eye tracking in a new thread
    threading.Thread(target=detect_pupil_movement).start()
    
    # Scrape a random Wikipedia paragraph
    random_url = random.choice(wikipedia_urls)
    last_title, last_paragraph, last_word_count = scrape_wikipedia_paragraph(random_url)

    for key in categories:
        l = categories[key]
        if random_url in l:
            correct_category = key

    return jsonify({
        'message': 'Eye tracker started, timer started',
        'paragraph': last_paragraph,
        'word_count': last_word_count
    })

@app.route('/stop_timer', methods=['POST'])
def stop_timer():
    global end_time, eye_tracking_active, user_id
    end_time = time.time()
    eye_tracking_active = False
    time_taken = end_time - start_time
    word_count = request.json.get('word_count')

    # Calculate base reading speed (words per minute)
    reading_speed = word_count / (time_taken / 60)

    # Adjust reading speed based on eye movements
    k = 0.1  
    if eye_movement_count > 0:
        adjusted_speed = reading_speed / (1 + k * math.log(1 + eye_movement_count))
    else:
        adjusted_speed = reading_speed  # Make sure to get user_id from request
    mongo.db.users.update_one(
        {'user_id': user_id},
        {'$set': {
            'reading_speed': reading_speed,
            'adjusted_reading_speed': adjusted_speed
        }}
    )

    return jsonify({
        'base_reading_speed': reading_speed, 
        'eye_movement_count': eye_movement_count,
        'adjusted_speed': adjusted_speed
    })

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    global correct_category  
    # Get random titles excluding the correct title
    url_list = [x for x in wikipedia_urls if x != random_url]
    random_titles = [url.split('/')[-1].replace('_', ' ').title() for url in url_list]
    
    # Ensure we have at least three other titles to choose from
    if len(random_titles) < 3:
        return jsonify({"error": "Not enough titles to generate options."}), 400

    # Randomly sample 3 titles from the available titles
    additional_titles = random.sample(random_titles, 3)

    # Combine the correct title with the additional titles
    title_options = [last_title] + additional_titles
    random.shuffle(title_options)  # Shuffle the options

    category_options = list(categories.keys())
    
    if request.method == 'POST':
        title_answer = request.form.get('question1')
        category_answer = request.form.get('question2')
        user_sentence = request.form.get('question3')

        # Calculate score
        score = 0
        correct_title = last_title

        if title_answer == correct_title:
            score += 1
        if category_answer == correct_category:
            score += 1

        # Calculate match percentage (comprehension result)
        match_percentage = calculate_match_percentage(last_paragraph, user_sentence)

        # Retrieve reading speeds from MongoDB
        user_data = mongo.db.users.find_one({'user_id': user_id})
        reading_speed = user_data['reading_speed']
        adjusted_reading_speed = user_data['adjusted_reading_speed']

        # Calculate total score (with match percentage)
        total_score = score + (match_percentage / 100)  # Score out of 3
        score_percentage = (total_score/3) * 100

        # Save the quiz results along with the date in MongoDB
        result = {
            'date': datetime.now(),  
            'title_answer': title_answer,
            'category_answer': category_answer,
            'user_sentence': user_sentence,
            'match_percentage': match_percentage,
            'score': total_score,
            'reading_speed': reading_speed,
            'adjusted_reading_speed': adjusted_reading_speed,
            'comprehension_result': score_percentage
        }
        mongo.db.users.update_one(
            {'user_id': user_id},
            {'$push': {'quiz_results': result}}  
        )

        # Redirect to the results page with all the necessary results
        return render_template(
            'results.html',
            reading_speed=reading_speed,
            adjusted_reading_speed=adjusted_reading_speed,
            total_score=total_score,  
            match_percentage=match_percentage,
            user_sentence=user_sentence,
            comprehension_result=score_percentage  # Add this line
        )

    return render_template(
        'quiz.html',
        title=last_title,
        word_count=last_word_count,
        paragraph=last_paragraph,
        title_options=title_options,
        category_options=category_options,
        total_score=None,  
        match_percentage=None  
    )

def calculate_match_percentage(original, user_input):
    # Combine the original paragraph and user input
    texts = [original, user_input]
    vectorizer = CountVectorizer().fit_transform(texts)
    vectors = vectorizer.toarray()
    cosine_sim = cosine_similarity(vectors)

    # Get the match percentage (1st element, 2nd element)
    return cosine_sim[0][1] * 100

def calculate_word_match_percentage(original, user_input):
    # Normalize the texts by converting to lowercase and splitting into words
    original_words = original.lower().split()
    user_input_words = user_input.lower().split()

    # Create a set of unique words from the original text
    original_set = set(original_words)

    # Count how many words in user input match the original
    match_count = sum(1 for word in user_input_words if word in original_set)

    # Calculate match percentage
    if len(original_words) == 0:
        return 0.0  # Avoid division by zero if original text is empty
    match_percentage = (match_count / len(original_words)) * 100

    return match_percentage


def detect_pupil_movement():
    global eye_tracking_active, eye_movement_count
    cap = cv2.VideoCapture(0)
    prev_x = None

    while eye_tracking_active:  # Start tracking if enabled
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        eyes = eye_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in eyes:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            pupil_center_x = x + w // 2  # Calculate the horizontal center of the pupil

            if prev_x is not None:
                # Check if the pupil has moved significantly horizontally
                if abs(pupil_center_x - prev_x) > 20:  # Threshold to detect significant movement
                    eye_movement_count += 1

            prev_x = pupil_center_x

        cv2.imshow('Eye Tracker', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    app.run(debug=True)
