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
    ai_reaction_text = ""
    loading_reaction = False
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
            "model": "deepseek/deepseek-chat-v3.1:free",
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

    # --- GET AI REACTION ---
    def get_ai_reaction(scenario_text, player_choice):
        global ai_last_error

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "deepseek/deepseek-chat-v3.1:free",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a high school student in a visual novel. "
                        "React naturally to the player's choice in one to two sentences. "
                        "If the player seems confident, respond warmly. "
                        "If they seem anxious, respond gently or awkwardly."
                        "Speak in the first person as the NPC."
                    )
                },
                {
                    "role": "user",
                    "content": f"Scenario: {scenario_text}\nPlayer chose: {player_choice}"
                }
            ],
            "temperature": 0.8,
            "max_output_tokens": 500
        }

        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            ai_text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return ai_text if ai_text else "(No reaction)"
        except Exception as e:
            ai_last_error = f"AI reaction error: {e}"
            renpy.log(ai_last_error)
            return "(AI failed to respond)"

    def get_ai_reaction_thread(scenario_text, player_choice):
        global ai_reaction_text, loading_reaction
        loading_reaction = True
        ai_reaction_text = get_ai_reaction(scenario_text, player_choice)
        loading_reaction = False

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

label ai_reaction(scenario_text, player_choice):
    $ import threading
    $ threading.Thread(target=get_ai_reaction_thread, args=(scenario_text, player_choice)).start()

    show screen ai_loading
    while loading_reaction:
        $ renpy.pause(0.1, hard=True)
    hide screen ai_loading

    # Return the AI’s text to the caller
    return ai_reaction_text

# ========================
# SCREENS
# ========================
screen ai_loading():
    if loading or loading_reaction:
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
            # 🔒 Locked choice
            if "🔒" in c["text"]:
                textbutton c["text"]:
                    background "#AAAAAA"
                    text_color "#555555"
                    insensitive_background "#AAAAAA"
                    padding (10, 10, 10, 10)
                    sensitive False
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
    
    "Act 1: It Begins to Unfold"
    "You wake up to a new day, ready for whatever comes next."
    "As you walk to the train station, you remember you actually haven't bought a ticket yet."
    "Shoot."
    "It's so early in the morning, you just stand in the middle of the station, until a staff member approaches you."
    "'What are you doing? Here to buy a ticket? You can use either the ticket machine or go to the ticket booth.' they ask."

    menu:
        "What do you do?"

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
    "It would be so embarrassing if you were wrong..."

    menu:
        "What do you do?"

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

    call ai_choice("A random person taps you on the shoulder, what do you say?", num_choices=3)
    $ selected_choice = _return

    "You chose: [selected_choice['text']] (+[selected_choice['points']] points, total: [player_points])"

    "Well, that was unexpected."
    "Whatever, you think to yourself as you continue walking to class."
    "I'm just a totally normal student after all."
    "Totally normal student with social anxiety, that is..."

    "As you enter the classroom, you go towards your seat."
    "Back left corner, as always. Hide from the world."
    "Or at least try to. Someone is already sitting there."
    "The only other empty seats are in the front row. Great."

    "{b}Depending on your choices so far, some dialogue options may be unlocked!{/b}"

    # --- Start AI loading manually ---
    $ import threading
    $ threading.Thread(target=get_ai_choices_thread, args=("Someone is sitting in your favourite seat, what do you do?", 3)).start()
    show screen ai_loading
    while loading:
        $ renpy.pause(0.1, hard=True)
    hide screen ai_loading

    # --- Add unlockable choice before showing screen ---
    if player_points >= 4:
        $ ai_choices.append({"text": "{b}Secret choice: Tell them to move it!{/b}", "points": 3})
    else:
        $ ai_choices.append({"text": "🔒 Tell them to move it! (Requires more confidence!)", "points": 0})

    if player_points < 0:
        $ ai_choices.append({"text": "{b}Secret choice: Silently stare at them until they go{/b}", "points": 1})
    else:
        $ ai_choices.append({"text": "🔒 Silently stare at them until they go (Requires less confidence!)", "points": 0})

    # --- Show the combined choice screen ---
    call screen ai_choice_screen(ai_choices)
    $ selected_choice = _return

    # --- Apply points ---
    $ player_points += selected_choice["points"]
    "You chose: [selected_choice['text']] (+[selected_choice['points']] points, total: [player_points])"

    "You see your friend sitting alone at lunch."
    $ scenario_text = "You see your friend sitting alone at lunch."
    menu:
        "What do you say? The AI will generate responses"

        "Sure, let's hang out!":
            $ player_choice = "Sure, let's hang out!"
            $ player_points += 2
            call ai_reaction(scenario_text, player_choice)
            $ ai_reaction_text = _return
        "I might study later.":
            $ player_choice = "I might study later."
            $ player_points += 0
            call ai_reaction(scenario_text, player_choice)
            $ ai_reaction_text = _return
        "No, I don't want to talk.":
            $ player_choice = "No, I don't want to talk."
            $ player_points += -2
            call ai_reaction(scenario_text, player_choice)
            $ ai_reaction_text = _return
    
    # Display the AI reaction
    "NPC: [ai_reaction_text]"
    "Your confidence points are now [player_points]."
    
    "And so continues another day in the life of a socially anxious high school student..."
    "The End...For Now."
