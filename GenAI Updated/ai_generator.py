import random
import os
import json

from google import genai
from dotenv import load_dotenv


# Loads the API key from the .env file so it is not sitting inside the code
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# Quick check so I know if the key is actually being picked up
print("ENV file loaded")

if GEMINI_API_KEY:
    print("Gemini key found")
    print("Key length:", len(GEMINI_API_KEY))
else:
    print("Gemini key NOT found")


# If the key exists, connect the program to Gemini
# If not, leave the AI client empty so the program does not crash straight away
if GEMINI_API_KEY:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    ai_client = None


"""
AI Question Generator for Phish n' Chips.

This section is mainly used to give the AI a bigger range of
questions instead of just focusing on Computing students.

It now includes:
- Different CSU study areas
- Different types of scenarios
- Different question types
- Easy, Medium and Hard questions
- Both phishing and legitimate examples
"""


# These are the different study areas the simulator can randomly choose from
STUDY_AREAS = [
    "Information Technology",
    "Computer Science",
    "Nursing",
    "Education",
    "Business",
    "Accounting",
    "Psychology",
    "Social Work",
    "Engineering",
    "Agriculture",
    "Environmental Science",
    "Health Science",
    "Law",
    "Communications",
    "Creative Arts",
    "Sport and Exercise Science"
]


# Each study area has its own pool of scenarios
# This helps make the training feel more relevant to different students
SCENARIOS = {
    "Information Technology": [
        "password reset",
        "software licence renewal",
        "cloud storage warning",
        "IT support request",
        "account security alert"
    ],

    "Computer Science": [
        "coding assignment submission",
        "Git repository access",
        "developer account warning",
        "cloud computing access",
        "group project invitation"
    ],

    "Nursing": [
        "clinical placement notification",
        "placement roster update",
        "training requirement",
        "health documentation request",
        "supervisor communication"
    ],

    "Education": [
        "teaching placement",
        "school placement update",
        "lesson plan submission",
        "assessment notification",
        "teaching resource access"
    ],

    "Business": [
        "internship opportunity",
        "group project",
        "invoice notification",
        "student payment",
        "business competition"
    ],

    "Accounting": [
        "tax workshop",
        "financial report submission",
        "invoice approval",
        "student payment",
        "internship notification"
    ],

    "Psychology": [
        "research participation",
        "placement notification",
        "survey invitation",
        "assessment update",
        "student support communication"
    ],

    "Social Work": [
        "community placement",
        "case study submission",
        "placement supervisor message",
        "training requirement",
        "community organisation notification"
    ],

    "Engineering": [
        "project submission",
        "laboratory access",
        "software licence",
        "group design project",
        "industry placement"
    ],

    "Agriculture": [
        "field placement",
        "farm visit",
        "research survey",
        "equipment booking",
        "industry placement"
    ],

    "Environmental Science": [
        "fieldwork notification",
        "research project",
        "laboratory booking",
        "equipment access",
        "field trip update"
    ],

    "Health Science": [
        "placement requirement",
        "training notification",
        "laboratory session",
        "student health documentation",
        "assessment submission"
    ],

    "Law": [
        "legal placement",
        "case study submission",
        "research database access",
        "student society notification",
        "assessment update"
    ],

    "Communications": [
        "media project",
        "group assignment",
        "portfolio submission",
        "event invitation",
        "internship opportunity"
    ],

    "Creative Arts": [
        "portfolio submission",
        "performance booking",
        "gallery event",
        "project collaboration",
        "assessment upload"
    ],

    "Sport and Exercise Science": [
        "practical session",
        "placement notification",
        "training event",
        "fitness assessment",
        "sports club communication"
    ]
}


# The AI can create different styles of questions instead of always asking the same thing
QUESTION_TYPES = [
    "True or False",
    "Multiple Choice",
    "Phishing or Legitimate",
    "What Would You Do?",
    "Trick Question"
]


# Gives us a simple difficulty system
DIFFICULTIES = [
    "Easy",
    "Medium",
    "Hard"
]


# Phishing appears slightly more often than legitimate messages
# This keeps the simulator focused on phishing training, but still includes some trickier safe examples
CLASSIFICATIONS = [
    "Phishing",
    "Phishing",
    "Phishing",
    "Legitimate",
    "Legitimate"
]


def generate_parameters():

    # Randomly choose a study area first
    study_area = random.choice(STUDY_AREAS)

    # Then choose a scenario that actually matches that study area
    scenario = random.choice(
        SCENARIOS[study_area]
    )

    # Randomly pick the type of question
    question_type = random.choice(
        QUESTION_TYPES
    )

    # Randomly pick how difficult it should be
    difficulty = random.choice(
        DIFFICULTIES
    )

    # Decide whether the example should be phishing or legitimate
    classification = random.choice(
        CLASSIFICATIONS
    )

    # Send all of the choices back together so Gemini can use them
    return {
        "study_area": study_area,
        "scenario": scenario,
        "question_type": question_type,
        "difficulty": difficulty,
        "classification": classification
    }


def generate_ai_question(parameters):

    # If there is no API key, stop here and return an error instead
    if ai_client is None:
        return {
            "error": "Gemini API key was not found."
        }

    # This is the main prompt that tells Gemini what kind of question we want
    # The random values from above are added into the prompt automatically
    prompt = f"""
You are the educational AI question generator for Phish n' Chips,
a university phishing-awareness training simulator.

Create ONE safe, fictional cybersecurity-awareness question for a
university student.

The selected parameters are:

Study Area: {parameters["study_area"]}
Scenario Context: {parameters["scenario"]}
Question Type: {parameters["question_type"]}
Difficulty: {parameters["difficulty"]}
Classification: {parameters["classification"]}

IMPORTANT RULES:

1. The scenario must be suitable for university students.
2. Make the scenario relevant to the selected study area where possible.
3. The scenario may be either phishing or legitimate according to the
   classification supplied above.
4. Do NOT automatically make every unusual message phishing.
5. Legitimate scenarios should still encourage safe verification.
6. Trick questions should genuinely require the student to think.
7. Do not use real passwords, private information or working malicious links.
8. Do not provide instructions for committing phishing or cybercrime.
9. The purpose is cybersecurity education and awareness.
10. Do not reveal the answer inside the scenario or question.

Question-type rules:

TRUE OR FALSE:
Create a statement or decision that the student must judge as True or False.

MULTIPLE CHOICE:
Provide exactly four possible answers.

PHISHING OR LEGITIMATE:
Ask the student to determine whether the simulated message is phishing
or legitimate.

WHAT WOULD YOU DO?:
Provide exactly four actions the student could take.

TRICK QUESTION:
Create a scenario where the obvious-looking answer may not necessarily
be correct. The student should need to examine context and choose the
safest response.

Return ONLY valid JSON using this structure:

{{
    "title": "Short title",
    "sender": "Fictional sender",
    "subject": "Simulated message subject",
    "message": "The simulated message shown to the student",
    "question": "The question the student must answer",
    "options": [
        "Option 1",
        "Option 2",
        "Option 3",
        "Option 4"
    ],
    "correct_answer": "Correct answer",
    "explanation": "Why this is the correct answer",
    "learning_point": "The cybersecurity lesson",
    "warning_signs": [
        "Warning sign 1",
        "Warning sign 2"
    ]
}}
"""

    try:

        # Send the finished prompt to Gemini
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        # Grab the text that Gemini sends back
        generated_text = response.text.strip()

        # Sometimes Gemini adds markdown around JSON
        # This removes it so Python can read the JSON properly
        generated_text = generated_text.replace("```json", "")
        generated_text = generated_text.replace("```", "")
        generated_text = generated_text.strip()

        # Turn the JSON text into something Python can work with
        return json.loads(generated_text)

    except Exception as e:

        # If Gemini fails, return the error instead of crashing the whole program
        return {
            "error": str(e)
        }


if __name__ == "__main__":

    # Generate a random setup for testing
    parameters = generate_parameters()

    print("\n--- Generated Parameters ---")

    print("Study Area:", parameters["study_area"])
    print("Scenario:", parameters["scenario"])
    print("Question Type:", parameters["question_type"])
    print("Difficulty:", parameters["difficulty"])
    print("Classification:", parameters["classification"])

    print("\n--- Asking Gemini ---")

    # Send those random settings to Gemini and print what comes back
    question = generate_ai_question(parameters)

    print(json.dumps(question, indent=4))