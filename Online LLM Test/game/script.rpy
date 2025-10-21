# ========================
# Initialisation
# ========================
init python:
    import requests
    import threading
    import json
    import traceback
    import time

    # --- API SETTINGS ---
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    API_KEY = "*"  # ← put your actual OpenRouter API key here
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds between retries

    # --- GAME STATE ---
    ai_choices = []
    loading = False
    dot_count = 0
    loading_text_base = "AI is thinking"
    player_points = 0
    max_points = 20
    ai_last_error = ""  # Store last error here

    # --- LOADING DOTS ---
    def increment_dots():
        global dot_count
        dot_count = (dot_count + 1) % 4

    def get_loading_text():
        return loading_text_base + "." * dot_count

    # --- CORE FUNCTION: Call DeepSeek API with retries ---
    def get_ai_choices_with_points(scenario_text, num_choices=3, min_points=-5, max_points=5):
        global ai_last_error
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "deepseek/deepseek-r1t2-chimera:free",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"You are a high school student in a visual novel. "
                        f"Generate exactly {num_choices} short dialogue responses the player can choose from. "
                        f"Each response should include a 'points' value between {min_points} and {max_points} representing confidence impact. "
                        f"Responses that involve asking for help always has positive points. "
                        f"There must also be at least one negative or neutral response. "
                        f"Return ONLY a JSON array with {num_choices} objects, no extra text or commentary. "
                        "Example format: "
                        "[{\"text\": \"Sure, let's hang out!\", \"points\": 2}, "
                        "{\"text\": \"I might study later.\", \"points\": 0}, "
                        "{\"text\": \"No, I don't want to talk.\", \"points\": -2}]"
                    )
                },
                {"role": "user", "content": scenario_text},
            ],
            "temperature": 1.0,
            "max_output_tokens": 500,
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                ai_text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

                if not ai_text:
                    ai_last_error = f"Empty response (attempt {attempt}/{MAX_RETRIES})"
                    renpy.log(f"AI WARNING: {ai_last_error}")
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                    continue

                # Try parsing JSON
                try:
                    choices = json.loads(ai_text)
                except json.JSONDecodeError:
                    start = ai_text.find("[")
                    end = ai_text.rfind("]") + 1
                    if start != -1 and end != -1:
                        choices = json.loads(ai_text[start:end])
                    else:
                        raise

                # --- Normalize result count ---
                if len(choices) < num_choices:
                    for i in range(len(choices), num_choices):
                        choices.append({"text": f"(No response {i+1})", "points": 0})
                elif len(choices) > num_choices:
                    choices = choices[:num_choices]

                ai_last_error = ""
                return choices

            except requests.exceptions.HTTPError as http_err:
                ai_last_error = f"HTTP error: {http_err} (attempt {attempt}/{MAX_RETRIES})"
                renpy.log(f"AI HTTP ERROR:\n{traceback.format_exc()}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
            except Exception as e:
                ai_last_error = f"Error: {e} (attempt {attempt}/{MAX_RETRIES})"
                renpy.log(f"AI ERROR:\n{traceback.format_exc()}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        # --- Fallback ---
        ai_last_error = f"DeepSeek failed after {MAX_RETRIES} attempts."
        return [{"text": "Stay silent.", "points": 0} for _ in range(num_choices)]

    # --- THREAD WRAPPER ---
    def get_ai_choices_thread(scenario_text, num_choices=3):
        global ai_choices, loading
        loading = True
        ai_choices = get_ai_choices_with_points(scenario_text, num_choices)
        loading = False


# ========================
# CALLABLE LABEL FOR AI CHOICES
# ========================
label ai_choice(scenario_text, num_choices=3):
    $ import threading
    $ threading.Thread(target=get_ai_choices_thread, args=(scenario_text, num_choices)).start()

    show screen ai_loading
    while loading:
        $ renpy.pause(0.1, hard=True)
    hide screen ai_loading

    call screen ai_choice_screen(ai_choices)
    $ selected_choice = _return
    $ player_points += selected_choice["points"]

    return selected_choice


# ========================
# SCREENS
# ========================
screen ai_loading():
    if loading:
        frame:
            xalign 0.5
            yalign 0.5
            padding (50, 50, 50, 50)
            text "[get_loading_text()]" size 40
        timer 0.5 action Function(increment_dots) repeat True

screen ai_choice_screen(choices):
    vbox:
        spacing 10
        xalign 0.5
        yalign 0.6
        for c in choices:
            if c["text"].startswith("(No response"):
                textbutton c["text"] action NullAction() sensitive False
            else:
                textbutton c["text"] action Return(c):
                    background "#FFFFFF"
                    padding (10, 10, 10, 10)
                    hover_background "#DDDDDD"

screen points_bar():
    frame:
        xalign 0.5
        yalign 0.05
        has vbox
        text "Relationship" xalign 0.5 size 20
        bar value player_points range max_points xmaximum 300

screen ai_error_display():
    if ai_last_error:
        frame:
            xalign 0.5
            yalign 0.95
            background "#330000AA"
            padding (10,10,10,10)
            text "AI Error: [ai_last_error]" color "#FFAAAA" size 18


# ========================
# MAIN STORY DEMO
# ========================
label start:
    show screen points_bar
    show screen ai_error_display
    image bg classroom = "images/school.jpg"

    scene bg classroom with fade

    "The classroom is quiet as you sit near the window."
    "Your classmate turns to you, smiling."
    "Your classmate asks: 'Hey, what are you doing after school?'"

    call ai_choice("Your classmate asks: 'Hey, what are you doing after school?'", num_choices=2)
    $ selected_choice = _return

    "You chose: [selected_choice['text']] (+[selected_choice['points']] points, total: [player_points])"

    if selected_choice["points"] >= 2:
        "Your classmate grins. 'Awesome! Let's go together.'"
    elif selected_choice["points"] >= 0:
        "They nod, seeming neutral about your answer."
    else:
        "You hesitate, unsure of what to say. The moment passes."

    "The bell rings, and the day continues."

    "Later that evening, your phone buzzes with a message from your classmate."
    "They text: 'Hey! Wanna talk more about today?'"

    call ai_choice("Your classmate texts: 'Hey! Wanna talk more about today?'", num_choices=4)
    $ selected_choice = _return

    "You replied: [selected_choice['text']] (+[selected_choice['points']] points, total: [player_points])"

    if selected_choice["points"] >= 2:
        "Your classmate quickly responds, 'Yay! Can't wait to hang out again soon!'"
    elif selected_choice["points"] >= 0:
        "They reply with a simple 'Thanks!'"
    else:
        "You don't respond, and the conversation fades away."

    if player_points >= 4:
        "You feel a strong connection forming with your classmate."
    else:
        "You wonder what tomorrow might bring."

    "Act 1: It Begins to Unfold"
    "You wake up to a new day, ready for whatever comes next."
    "As you walk to the train station, you remember you actually haven't bought a ticket yet."
    "Shoot."
    "It's so early in the morning, you just stand in the middle of the station, until a staff member approaches you."
    "'What are you doing? Here to buy a ticket? You can use either the ticket machine or go to the ticket booth.' they ask."

    menu:
        "Go to the ticket machine.":
            "You head over to the ticket machine and quickly purchase your ticket."
            "Feeling relieved, you make your way to the platform."
        "Go to the ticket booth.":
            "You nervously ask the staff member at the ticket booth to buy a ticket."
            "'Of course! Let me get you a return ticket.' they say kindly."
            "Grateful, you get your ticket, feeling slightly more confident."
            $ player_points += 2
            "Your confidence points increased to [player_points]."

    "Phew, that was close."
    "As you rush to the platform, you see the train arriving."
    "You get on, finding a seat by the window."
    "Out of the corner of your eye, you notice someone familiar boarding the train."
    "At least, you think you recognize them?"
    "What do you do? It would be so embarrassing if you were wrong..."

    menu:
        "Ignore them and stay in your seat.":
            "You decide it's best not to make a scene."
            "The train ride continues uneventfully."
        "Get up and approach them.":
            "You muster your courage and walk over."
            "'Hey, aren't you in my class?' you ask."
            "They smile, 'Yeah, I thought I recognized you!'"
            "You both chat for the rest of the ride, making plans to hang out after school."
            "{b} Unlocked a new friendship! {/b}"
            $ player_points += 3
            "Your confidence points increased to [player_points]."

    "As the train pulls into your stop, you gather your things and head out."
    "You begin to walk to class at a normal pace."
    "This isn't a typical anime episode where you're late and have to sprint to make it on time."
    "Suddenly, you feel a tap on your shoulder."
    "Panicking, you turn around to see...a random person?!"

    call ai_choice("A random person taps you on the shoulder, what do you do?", num_choices=3)
    $ selected_choice = _return

    "You chose: [selected_choice['text']] (+[selected_choice['points']] points, total: [player_points])"

    "The end."
    return
