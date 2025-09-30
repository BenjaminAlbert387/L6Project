# ========================
# AI Choice System
# ========================
init python:
    import requests
    import threading
    import json

    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    API_KEY = "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"  # Replace with your actual key

    ai_choices = []
    loading = False
    dot_count = 0
    loading_text_base = "AI is thinking"
    player_points = 0
    max_points = 10  # Example maximum points

    # Call API and return choices
    def get_ai_choices_with_points(scenario_text):
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "x-ai/grok-4-fast:free",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a high school student in a visual novel. "
                        "Generate exactly 3 short dialogue responses the player can choose from. "
                        "Each response should have a 'points' value (-5 to +5) representing how it affects the relationship with the classmate. "
                        "Return the output as valid JSON like this: "
                        '[{\"text\": \"Sure, let\'s hang out!\", \"points\": 2}, '
                        '{\"text\": \"I might study later.\", \"points\": 0}, '
                        '{\"text\": \"No, I don\'t want to talk.\", \"points\": -2}]'
                    )
                },
                {"role": "user", "content": scenario_text}
            ],
            "temperature": 1.0,
            "max_tokens": 200,
        }

        try:
            resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            ai_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not ai_text:
                raise ValueError("Empty response from API")

            choices = json.loads(ai_text)
            while len(choices) < 3:
                choices.append({"text": "...", "points": 0})
            return choices[:3]

        except Exception as e:
            renpy.log(f"Grok 4 API failed: {e}")
            return [
                {"text": "(Error contacting AI)", "points": 0},
                {"text": "Stay silent.", "points": 0},
                {"text": "Change topic.", "points": 0},
            ]

    def get_ai_choices_thread(scenario_text):
        global ai_choices, loading
        loading = True
        ai_choices = get_ai_choices_with_points(scenario_text)
        loading = False

    def increment_dots():
        global dot_count
        dot_count = (dot_count + 1) % 4

    def get_loading_text():
        return loading_text_base + "." * dot_count

# ========================
# Screens
# ========================
screen ai_loading():
    if loading:
        frame:
            xalign 0.5
            yalign 0.5
            text "[get_loading_text()]" size 40
        timer 0.5 action Function(increment_dots) repeat True

screen ai_choice_screen(choices):
    vbox:
        spacing 10
        for c in choices:
            textbutton c["text"] action Return(c)

screen points_bar():
    frame:
        xalign 0.5
        yalign 0.05
        has vbox

        text "Relationship" xalign 0.5 size 20

        bar value player_points range max_points xmaximum 300

# ========================
# Callable AI Choice Label
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
# Main Story
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

    "You begin to walk home, thinking about your conversation."
    "Suddenly, your phone buzzes with a message from your classmate."
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
    return
