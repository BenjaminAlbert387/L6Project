# ========================
# AI Choice System (DeepSeek v3.1 Free)
# ========================
init python:
    import requests
    import threading
    import json

    # --- API SETTINGS ---
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    API_KEY = "*"  # <- Put the real API key here

    # --- GAME STATE ---
    ai_choices = []
    loading = False
    dot_count = 0
    loading_text_base = "AI is thinking"
    player_points = 0
    max_points = 10
    last_error_message = ""  # Stores last exception for in-game display

    # --- CORE FUNCTION: Call API and return 3 choices ---
    def get_ai_choices_with_points(scenario_text):
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
                        "Generate exactly 3 short dialogue responses the player can choose from. "
                        "Each response should include a 'points' value (-5 to +5) representing relationship impact. "
                        "Return the output as valid JSON like this: "
                        "[{\"text\": \"Sure, let's hang out!\", \"points\": 2}, "
                        "{\"text\": \"I might study later.\", \"points\": 0}, "
                        "{\"text\": \"No, I don't want to talk.\", \"points\": -2}]"
                    )
                },
                {"role": "user", "content": scenario_text},
            ],
            "temperature": 1.0,
            "max_output_tokens": 250,
        }

        try:
            resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            ai_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not ai_text:
                raise ValueError("Empty response from API")

            # Try parsing JSON from model output
            try:
                choices = json.loads(ai_text)
            except json.JSONDecodeError:
                # If model added extra text, try to extract JSON substring
                start = ai_text.find("[")
                end = ai_text.rfind("]") + 1
                choices = json.loads(ai_text[start:end])

            while len(choices) < 3:
                choices.append({"text": "...", "points": 0})
                last_error_message = ""  # Clear previous errors on success
            return choices[:3]

        except Exception as e:
            last_error_message = str(e)  # Save exception to display in-game
            renpy.log(f"AI request failed: {e}")
            return [
                {"text": "(Error contacting AI)", "points": 0},
                {"text": "Stay silent.", "points": 0},
                {"text": "Change topic.", "points": 0},
            ]

    # --- THREAD WRAPPER ---
    def get_ai_choices_thread(scenario_text):
        global ai_choices, loading
        loading = True
        ai_choices = get_ai_choices_with_points(scenario_text)
        loading = False

    # --- LOADING DOTS ---
    def increment_dots():
        global dot_count
        dot_count = (dot_count + 1) % 4

    def get_loading_text():
        return loading_text_base + "." * dot_count


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
            textbutton c["text"] action Return(c)

screen points_bar():
    frame:
        xalign 0.5
        yalign 0.05
        has vbox
        text "Relationship" xalign 0.5 size 20
        bar value player_points range max_points xmaximum 300

screen ai_error():
    if last_error_message:
        frame:
            xalign 0.5
            yalign 0.9
            padding (10, 10, 10, 10)
            background "#550000AA"
            text "[last_error_message]" size 20 color "#ff5555"


# ========================
# CALLABLE LABEL FOR AI CHOICES
# ========================
label ai_choice(scenario_text):
    $ threading.Thread(target=get_ai_choices_thread, args=(scenario_text,)).start()

    show screen ai_loading
    while loading:
        $ renpy.pause(0.1, hard=True)
    hide screen ai_loading

    call screen ai_choice_screen(ai_choices)
    $ selected_choice = _return
    $ player_points += selected_choice["points"]

    return selected_choice


# ========================
# MAIN STORY DEMO
# ========================
label start:
    show screen points_bar
    scene bg classroom
    with fade

    "The classroom is quiet as you sit near the window."
    "Your classmate turns to you, smiling."
    "Your classmate asks: 'Hey, what are you doing after school?'"

    call ai_choice("Your classmate asks: 'Hey, what are you doing after school?'")
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
    "They text: 'Hey, just wanted to say I had a great time today!'"

    call ai_choice("Your classmate texts: 'Hey, just wanted to say I had a great time today!'")
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

    return
