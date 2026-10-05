from flask import Flask, render_template, request, redirect, url_for, session, flash
import joblib
from datetime import datetime
from database import init_database, get_db_connection

app = Flask(__name__)
app.secret_key = "ai_wellness_secret_key"


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

init_database()


def ensure_energy_column():
    """
    Adds energy_level to old databases without deleting
    existing users, predictions or goals.
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "ALTER TABLE mood_predictions ADD COLUMN energy_level REAL"
        )
    except Exception:
        # Column already exists
        pass

    conn.commit()
    conn.close()


ensure_energy_column()


# =========================================================
# LOAD ML MODEL
# =========================================================

model = joblib.load("mood_model.pkl")


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_mood_emoji(mood):

    mood = str(mood).lower()

    if mood == "happy":
        return "😊"

    elif mood == "sad":
        return "😔"

    elif mood == "tired":
        return "😴"

    elif mood == "anxious":
        return "😟"

    elif mood == "angry":
        return "😡"

    elif mood == "neutral":
        return "😐"

    return "🙂"


# =========================================================
# WELLNESS SCORE
# =========================================================

def calculate_wellness_score(
    sleep_hours,
    stress_level,
    screen_time,
    exercise_minutes,
    energy_level
):

    sleep_score = min(
        (sleep_hours / 8) * 100,
        100
    )

    stress_score = max(
        0,
        100 - (stress_level * 10)
    )

    screen_score = max(
        0,
        100 - ((screen_time / 12) * 100)
    )

    exercise_score = min(
        (exercise_minutes / 30) * 100,
        100
    )

    energy_score = energy_level * 10

    wellness_score = (
        sleep_score * 0.25
        + stress_score * 0.25
        + screen_score * 0.15
        + exercise_score * 0.15
        + energy_score * 0.20
    )

    return round(wellness_score, 1)


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("index.html")


# ---------------------------------------------------
# REGISTER
# ---------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Check empty fields
        if not name or not email or not password:
            flash("Please fill all fields.", "error")
            return redirect(url_for("register"))

        conn = get_db_connection()

        try:

            # Check whether email already exists
            existing_user = conn.execute(
                """
                SELECT id
                FROM users
                WHERE email = ?
                """,
                (email,)
            ).fetchone()

            if existing_user:
                flash(
                    "This email is already registered. Please login.",
                    "error"
                )
                return redirect(url_for("register"))

            # Create new account
            conn.execute(
                """
                INSERT INTO users
                (name, email, password)
                VALUES (?, ?, ?)
                """,
                (name, email, password)
            )

            conn.commit()

            flash(
                "Account created successfully! Please login.",
                "success"
            )

            return redirect(url_for("login"))

        except Exception as e:

            print("REGISTER ERROR:", e)

            flash(
                "Unable to create account. Please try again.",
                "error"
            )

            return redirect(url_for("register"))

        finally:

            conn.close()

    return render_template("register.html")

# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            AND password = ?
            """,
            (
                email,
                password
            )
        ).fetchone()

        conn.close()

        if user:

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid email or password.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email")

        new_password = request.form.get(
            "new_password"
        )

        if not email or not new_password:

            flash(
                "Please enter email and new password.",
                "error"
            )

            return redirect(
                url_for("forgot_password")
            )

        conn = get_db_connection()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if user:

            conn.execute(
                """
                UPDATE users
                SET password = ?
                WHERE email = ?
                """,
                (
                    new_password,
                    email
                )
            )

            conn.commit()

            conn.close()

            flash(
                "Password changed successfully!",
                "success"
            )

            return redirect(
                url_for("login")
            )

        conn.close()

        flash(
            "Email not found.",
            "error"
        )

        return redirect(
            url_for("forgot_password")
        )

    return render_template(
        "forgot_password.html"
    )


# =========================================================
# PREDICTION
# =========================================================

@app.route(
    "/predict",
    methods=["GET", "POST"]
)
def predict():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        try:

            # -------------------------------
            # SLEEP
            # -------------------------------

            sleep_hours = float(
                request.form.get(
                    "sleep_hours"
                )
            )

            # -------------------------------
            # STRESS
            # -------------------------------

            stress_level = float(
                request.form.get(
                    "stress_level"
                )
            )

            # -------------------------------
            # SCREEN TIME
            # Supports new split fields
            # and old single field
            # -------------------------------

            screen_hours = request.form.get(
                "screen_hours"
            )

            screen_minutes = request.form.get(
                "screen_minutes"
            )

            if (
                screen_hours is not None
                and screen_minutes is not None
            ):

                screen_time = (
                    float(screen_hours)
                    + float(screen_minutes) / 60
                )

            else:

                screen_time = float(
                    request.form.get(
                        "screen_time"
                    )
                )

            # -------------------------------
            # EXERCISE
            # Supports split fields
            # and old single field
            # -------------------------------

            exercise_hours = request.form.get(
                "exercise_hours"
            )

            exercise_minutes_input = request.form.get(
                "exercise_minutes"
            )

            if (
                exercise_hours is not None
                and exercise_minutes_input is not None
            ):

                exercise_minutes = (
                    float(exercise_hours) * 60
                    + float(exercise_minutes_input)
                )

            else:

                exercise_minutes = float(
                    request.form.get(
                        "exercise_minutes"
                    )
                )

            # -------------------------------
            # ENERGY
            # -------------------------------

            energy_level = float(
                request.form.get(
                    "energy_level"
                )
            )

        except (
            TypeError,
            ValueError
        ):

            flash(
                "Please enter valid values.",
                "error"
            )

            return redirect(
                url_for("predict")
            )

        # =================================================
        # VALIDATION
        # =================================================

        if not 1 <= sleep_hours <= 12:

            flash(
                "Sleep hours must be between 1 and 12.",
                "error"
            )

            return redirect(
                url_for("predict")
            )

        if not 1 <= stress_level <= 10:

            flash(
                "Stress level must be between 1 and 10.",
                "error"
            )

            return redirect(
                url_for("predict")
            )

        if not 0 <= screen_time <= 12:

            flash(
                "Screen time must be between 0 and 12 hours.",
                "error"
            )

            return redirect(
                url_for("predict")
            )

        if not 0 <= exercise_minutes <= 720:

            flash(
                "Exercise must be between 0 and 720 minutes.",
                "error"
            )

            return redirect(
                url_for("predict")
            )

        if not 1 <= energy_level <= 10:

            flash(
                "Energy level must be between 1 and 10.",
                "error"
            )

            return redirect(
                url_for("predict")
            )

        # =================================================
        # ML PREDICTION
        # =================================================

        input_data = [[
            sleep_hours,
            stress_level,
            screen_time,
            exercise_minutes,
            energy_level
        ]]

        prediction = model.predict(
            input_data
        )[0]

        mood = str(prediction)

        # =================================================
        # CONFIDENCE
        # =================================================

        confidence = None

        try:

            probabilities = model.predict_proba(
                input_data
            )

            confidence = round(
                max(probabilities[0]) * 100,
                1
            )

        except Exception:

            confidence = None

        # =================================================
        # WELLNESS SCORE
        # =================================================

        wellness_score = calculate_wellness_score(
            sleep_hours,
            stress_level,
            screen_time,
            exercise_minutes,
            energy_level
        )

        # =================================================
        # DATE & TIME
        # =================================================

        now = datetime.now()

        prediction_date = now.strftime(
            "%Y-%m-%d"
        )

        prediction_time = now.strftime(
            "%H:%M:%S"
        )

        # =================================================
        # SAVE PREDICTION
        # =================================================

        conn = get_db_connection()

        conn.execute(
            """
            INSERT INTO mood_predictions
            (
                user_id,
                sleep_hours,
                stress_level,
                screen_time,
                exercise_minutes,
                mood,
                prediction_date,
                prediction_time,
                wellness_score,
                energy_level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                sleep_hours,
                stress_level,
                screen_time,
                exercise_minutes,
                mood,
                prediction_date,
                prediction_time,
                wellness_score,
                energy_level
            )
        )

        conn.commit()

        conn.close()

        # =================================================
        # AI CONSULTANT SUGGESTIONS
        # =================================================

        suggestions = []

        # Sleep

        if sleep_hours < 6:

            suggestions.append(
                "Try to get more sleep. Aim for around 7–9 hours of sleep."
            )

        elif sleep_hours > 10:

            suggestions.append(
                "You are sleeping for a long duration. Maintain a consistent sleep schedule."
            )

        else:

            suggestions.append(
                "Your sleep duration looks reasonable. Maintain a regular sleep routine."
            )

        # Stress

        if stress_level >= 7:

            suggestions.append(
                "Your stress level is high. Try deep breathing, meditation, or a short relaxing break."
            )

        elif stress_level >= 4:

            suggestions.append(
                "Your stress level is moderate. Take regular breaks and include relaxing activities."
            )

        else:

            suggestions.append(
                "Your stress level is relatively low. Continue maintaining healthy stress-management habits."
            )

        # Screen

        if screen_time > 6:

            suggestions.append(
                "Your screen time is high. Consider taking regular screen breaks."
            )

        else:

            suggestions.append(
                "Your screen time is within a reasonable range. Continue taking regular breaks."
            )

        # Exercise

        if exercise_minutes < 20:

            suggestions.append(
                "Try adding some physical activity such as walking, stretching, or light exercise."
            )

        else:

            suggestions.append(
                "Good job staying physically active. Continue maintaining regular exercise."
            )

        # Energy

        if energy_level <= 3:

            suggestions.append(
                "Your energy level is low. Focus on adequate rest, hydration, nutrition, and relaxation."
            )

        elif energy_level >= 8:

            suggestions.append(
                "Your energy level is high. Use this energy for productive and enjoyable activities."
            )

        else:

            suggestions.append(
                "Your energy level is moderate. Maintain balanced sleep, exercise, and daily routines."
            )

        # =================================================
        # MOOD MESSAGE
        # =================================================

        mood_lower = mood.lower()

        if mood_lower == "happy":

            mood_message = (
                "You appear to be feeling happy. "
                "Keep doing activities that support your positive mood."
            )

        elif mood_lower == "sad":

            mood_message = (
                "You may be experiencing a low mood. "
                "Consider talking to someone you trust and spending time on activities you enjoy."
            )

        elif mood_lower == "tired":

            mood_message = (
                "You may be feeling tired. "
                "Prioritize rest, good sleep, hydration, and short breaks."
            )

        elif mood_lower == "anxious":

            mood_message = (
                "You may be experiencing anxiety. "
                "Try slow breathing, relaxation exercises, and reducing unnecessary stressors."
            )

        elif mood_lower == "angry":

            mood_message = (
                "You may be experiencing anger or frustration. "
                "Take some time to pause, breathe, and step away from stressful situations."
            )

        else:

            mood_message = (
                "Your mood appears relatively balanced. "
                "Continue maintaining healthy daily habits."
            )

        return render_template(
            "result.html",
            mood=mood,
            emoji=get_mood_emoji(mood),
            confidence=confidence,
            wellness_score=wellness_score,
            suggestions=suggestions,
            mood_message=mood_message
        )

    return render_template(
        "predict.html"
    )


# ---------------------------------------------------
# DASHBOARD
# ---------------------------------------------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db_connection()

    # =================================================
    # GET USER PREDICTIONS
    # =================================================

    predictions = conn.execute(
        """
        SELECT *
        FROM mood_predictions
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    # =================================================
    # GET USER GOALS
    # If no goals exist, create default goals
    # =================================================

    goals = conn.execute(
        """
        SELECT *
        FROM wellness_goals
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    if goals is None:

        conn.execute(
            """
            INSERT INTO wellness_goals
            (
                user_id,
                sleep_goal,
                exercise_goal,
                screen_time_goal,
                stress_goal,
                energy_goal
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                8,
                30,
                5,
                4,
                7
            )
        )

        conn.commit()

        goals = conn.execute(
            """
            SELECT *
            FROM wellness_goals
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()

    conn.close()

    # =================================================
    # TOTAL PREDICTIONS
    # =================================================

    total_predictions = len(predictions)

    # =================================================
    # AVERAGE VALUES
    # =================================================

    if total_predictions > 0:

        avg_wellness = round(
            sum(
                float(p["wellness_score"] or 0)
                for p in predictions
            ) / total_predictions,
            1
        )

        avg_sleep = round(
            sum(
                float(p["sleep_hours"] or 0)
                for p in predictions
            ) / total_predictions,
            1
        )

        avg_stress = round(
            sum(
                float(p["stress_level"] or 0)
                for p in predictions
            ) / total_predictions,
            1
        )

        avg_screen = round(
            sum(
                float(p["screen_time"] or 0)
                for p in predictions
            ) / total_predictions,
            1
        )

        avg_exercise = round(
            sum(
                float(p["exercise_minutes"] or 0)
                for p in predictions
            ) / total_predictions,
            1
        )

        # Energy may be NULL for older predictions
        energy_values = []

        for p in predictions:
            try:
                if p["energy_level"] is not None:
                    energy_values.append(
                        float(p["energy_level"])
                    )
            except (IndexError, KeyError):
                pass

        if energy_values:
            avg_energy = round(
                sum(energy_values) / len(energy_values),
                1
            )
        else:
            avg_energy = 0

    else:

        avg_wellness = 0
        avg_sleep = 0
        avg_stress = 0
        avg_screen = 0
        avg_exercise = 0
        avg_energy = 0

    # =================================================
    # MOOD DISTRIBUTION
    # =================================================

    mood_counts = {}

    for p in predictions:

        mood = p["mood"]

        mood_counts[mood] = (
            mood_counts.get(mood, 0) + 1
        )

    mood_labels = list(mood_counts.keys())
    mood_values = list(mood_counts.values())

    # =================================================
    # WELLNESS TREND
    # =================================================

    trend_labels = []
    trend_values = []
    trend_ids = []

    # Reverse so graph shows oldest → newest
    for p in reversed(predictions):

        date_value = p["prediction_date"]

        time_value = p["prediction_time"] or ""

        # Graph label
        label = f"{date_value} {time_value}"

        trend_labels.append(label)

        trend_values.append(
            float(p["wellness_score"] or 0)
        )

        # Used to highlight the matching
        # prediction history row
        trend_ids.append(p["id"])

    # =================================================
    # GOAL TRACKING
    # =================================================

    achieved_goals = []

    attention_goals = []

    goal_notifications = []

    # -------------------------------------------------
    # SLEEP GOAL
    # -------------------------------------------------

    sleep_goal = float(
        goals["sleep_goal"] or 8
    )

    if total_predictions > 0:

        if avg_sleep >= sleep_goal:

            achieved_goals.append("sleep")

        else:

            attention_goals.append("sleep")

            goal_notifications.append(
                f"Sleep goal: Try to reach {sleep_goal:.1f} hours."
            )

    # -------------------------------------------------
    # EXERCISE GOAL
    # -------------------------------------------------

    exercise_goal = float(
        goals["exercise_goal"] or 30
    )

    if total_predictions > 0:

        if avg_exercise >= exercise_goal:

            achieved_goals.append("exercise")

        else:

            attention_goals.append("exercise")

            goal_notifications.append(
                f"Exercise goal: Try to reach {exercise_goal:.0f} minutes."
            )

    # -------------------------------------------------
    # SCREEN TIME GOAL
    # -------------------------------------------------

    screen_goal = float(
        goals["screen_time_goal"] or 5
    )

    if total_predictions > 0:

        if avg_screen <= screen_goal:

            achieved_goals.append("screen")

        else:

            attention_goals.append("screen")

            goal_notifications.append(
                f"Screen time goal: Try to stay below {screen_goal:.1f} hours."
            )

    # -------------------------------------------------
    # STRESS GOAL
    # -------------------------------------------------

    stress_goal = float(
        goals["stress_goal"] or 4
    )

    if total_predictions > 0:

        if avg_stress <= stress_goal:

            achieved_goals.append("stress")

        else:

            attention_goals.append("stress")

            goal_notifications.append(
                f"Stress goal: Try to keep stress below {stress_goal:.1f}."
            )

    # -------------------------------------------------
    # ENERGY GOAL
    # -------------------------------------------------

    energy_goal = float(
        goals["energy_goal"] or 7
    )

    if avg_energy > 0:

        if avg_energy >= energy_goal:

            achieved_goals.append("energy")

        else:

            attention_goals.append("energy")

            goal_notifications.append(
                f"Energy goal: Try to reach {energy_goal:.1f}."
            )

    # =================================================
    # RENDER DASHBOARD
    # =================================================

    return render_template(
        "dashboard.html",

        # User
        user_name=session.get("user_name"),

        # Main statistics
        total_predictions=total_predictions,
        avg_wellness=avg_wellness,
        avg_sleep=avg_sleep,
        avg_stress=avg_stress,
        avg_screen=avg_screen,
        avg_exercise=avg_exercise,
        avg_energy=avg_energy,

        # Charts
        mood_labels=mood_labels,
        mood_values=mood_values,

        trend_labels=trend_labels,
        trend_values=trend_values,
        trend_ids=trend_ids,

        # Prediction history
        predictions=predictions,

        # Goals
        goals=goals,
        achieved_goals=achieved_goals,
        attention_goals=attention_goals,
        goal_notifications=goal_notifications
    )

    # =================================================
    # TOTAL
    # =================================================

    total_predictions = len(
        predictions
    )

    # =================================================
    # AVERAGES
    # =================================================

    if total_predictions > 0:

        avg_wellness = round(
            sum(
                p["wellness_score"]
                for p in predictions
            ) / total_predictions,
            1
        )

        avg_sleep = round(
            sum(
                p["sleep_hours"]
                for p in predictions
            ) / total_predictions,
            1
        )

        avg_stress = round(
            sum(
                p["stress_level"]
                for p in predictions
            ) / total_predictions,
            1
        )

        avg_screen = round(
            sum(
                p["screen_time"]
                for p in predictions
            ) / total_predictions,
            1
        )

        avg_exercise = round(
            sum(
                p["exercise_minutes"]
                for p in predictions
            ) / total_predictions,
            1
        )

        energy_values = [
            p["energy_level"]
            for p in predictions
            if p["energy_level"] is not None
        ]

        if energy_values:

            avg_energy = round(
                sum(energy_values)
                / len(energy_values),
                1
            )

        else:

            avg_energy = 0

    else:

        avg_wellness = 0
        avg_sleep = 0
        avg_stress = 0
        avg_screen = 0
        avg_exercise = 0
        avg_energy = 0

    # =================================================
    # MOOD DISTRIBUTION
    # =================================================

    mood_counts = {}

    for p in predictions:

        mood = p["mood"]

        mood_counts[mood] = (
            mood_counts.get(mood, 0) + 1
        )

    mood_labels = list(
        mood_counts.keys()
    )

    mood_values = list(
        mood_counts.values()
    )

    # =================================================
    # WELLNESS TREND
    # =================================================

    trend_labels = []
    trend_values = []
    trend_ids = []

    for p in reversed(predictions):

        date_value = p[
            "prediction_date"
        ]

        time_value = p[
            "prediction_time"
        ] or ""

        label = (
            f"{date_value} "
            f"{time_value}"
        )

        trend_labels.append(
            label
        )

        trend_values.append(
            p["wellness_score"]
        )

        # IMPORTANT:
        # Used to identify exact history row

        trend_ids.append(
            p["id"]
        )

    # =================================================
    # GOAL TRACKING
    # =================================================

    achieved_goals = []

    attention_goals = []

    goal_notifications = []

    if goals:

        # Sleep

        if avg_sleep >= goals["sleep_goal"]:

            achieved_goals.append(
                "sleep"
            )

        else:

            attention_goals.append(
                "sleep"
            )

            goal_notifications.append(
                f"Sleep goal: Try to reach "
                f"{goals['sleep_goal']} hours."
            )

        # Exercise

        if avg_exercise >= goals["exercise_goal"]:

            achieved_goals.append(
                "exercise"
            )

        else:

            attention_goals.append(
                "exercise"
            )

            goal_notifications.append(
                f"Exercise goal: Try to reach "
                f"{goals['exercise_goal']} minutes."
            )

        # Screen

        if avg_screen <= goals["screen_time_goal"]:

            achieved_goals.append(
                "screen"
            )

        else:

            attention_goals.append(
                "screen"
            )

            goal_notifications.append(
                f"Screen time goal: Try to stay below "
                f"{goals['screen_time_goal']} hours."
            )

        # Stress

        if avg_stress <= goals["stress_goal"]:

            achieved_goals.append(
                "stress"
            )

        else:

            attention_goals.append(
                "stress"
            )

            goal_notifications.append(
                f"Stress goal: Try to keep stress below "
                f"{goals['stress_goal']}."
            )

        # Energy

        if avg_energy >= goals["energy_goal"]:

            achieved_goals.append(
                "energy"
            )

        else:

            attention_goals.append(
                "energy"
            )

            goal_notifications.append(
                f"Energy goal: Try to reach "
                f"{goals['energy_goal']}."
            )

    # =================================================
    # RENDER DASHBOARD
    # =================================================

    return render_template(

        "dashboard.html",

        user_name=session.get(
            "user_name",
            "User"
        ),

        total_predictions=
            total_predictions,

        avg_wellness=
            avg_wellness,

        avg_sleep=
            avg_sleep,

        avg_stress=
            avg_stress,

        avg_screen=
            avg_screen,

        avg_exercise=
            avg_exercise,

        avg_energy=
            avg_energy,

        mood_labels=
            mood_labels,

        mood_values=
            mood_values,

        trend_labels=
            trend_labels,

        trend_values=
            trend_values,

        trend_ids=
            trend_ids,

        predictions=
            predictions,

        goals=
            goals,

        achieved_goals=
            achieved_goals,

        attention_goals=
            attention_goals,

        goal_notifications=
            goal_notifications
    )


# =========================================================
# WELLNESS GOALS
# =========================================================

@app.route(
    "/goals",
    methods=["GET", "POST"]
)
def goals():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    if request.method == "POST":

        try:

            # -----------------------------
            # SLEEP GOAL
            # -----------------------------

            sleep_goal = float(
                request.form.get(
                    "sleep_goal"
                )
            )


            # -----------------------------
            # STRESS GOAL
            # -----------------------------

            stress_goal = float(
                request.form.get(
                    "stress_goal"
                )
            )


            # -----------------------------
            # ENERGY GOAL
            # -----------------------------

            energy_goal = float(
                request.form.get(
                    "energy_goal"
                )
            )


            # -----------------------------
            # SCREEN TIME GOAL
            # Hours + Minutes
            # -----------------------------

            screen_hours = int(
                request.form.get(
                    "screen_hours",
                    0
                )
            )

            screen_minutes = int(
                request.form.get(
                    "screen_minutes",
                    0
                )
            )

            screen_time_goal = round(
                screen_hours +
                (screen_minutes / 60),
                2
            )


            # -----------------------------
            # EXERCISE GOAL
            # Hours + Minutes
            # -----------------------------

            exercise_hours = int(
                request.form.get(
                    "exercise_hours",
                    0
                )
            )

            exercise_minutes = int(
                request.form.get(
                    "exercise_minutes",
                    0
                )
            )

            exercise_goal = (
                exercise_hours * 60
            ) + exercise_minutes


            # -----------------------------
            # VALIDATION
            # -----------------------------

            if sleep_goal < 1 or sleep_goal > 12:
                raise ValueError

            if stress_goal < 1 or stress_goal > 10:
                raise ValueError

            if energy_goal < 1 or energy_goal > 10:
                raise ValueError

            if screen_time_goal < 0 or screen_time_goal > 12:
                raise ValueError

            if exercise_goal < 0 or exercise_goal > 720:
                raise ValueError


        except (
            TypeError,
            ValueError
        ):

            flash(
                "Please enter valid goal values.",
                "error"
            )

            return redirect(
                url_for("goals")
            )


        # -----------------------------
        # DATABASE
        # -----------------------------

        conn = get_db_connection()

        existing = conn.execute(
            """
            SELECT id
            FROM wellness_goals
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()


        if existing:

            conn.execute(
                """
                UPDATE wellness_goals
                SET
                    sleep_goal = ?,
                    exercise_goal = ?,
                    screen_time_goal = ?,
                    stress_goal = ?,
                    energy_goal = ?
                WHERE user_id = ?
                """,
                (
                    sleep_goal,
                    exercise_goal,
                    screen_time_goal,
                    stress_goal,
                    energy_goal,
                    user_id
                )
            )


        else:

            conn.execute(
                """
                INSERT INTO wellness_goals
                (
                    user_id,
                    sleep_goal,
                    exercise_goal,
                    screen_time_goal,
                    stress_goal,
                    energy_goal
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    sleep_goal,
                    exercise_goal,
                    screen_time_goal,
                    stress_goal,
                    energy_goal
                )
            )


        conn.commit()

        conn.close()


        flash(
            "Wellness goals saved successfully!",
            "success"
        )

        return redirect(
            url_for("goals")
        )


    # -----------------------------
    # GET CURRENT GOALS
    # -----------------------------

    conn = get_db_connection()

    goals_data = conn.execute(
        """
        SELECT *
        FROM wellness_goals
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.close()


    return render_template(
        "goals.html",
        goals=goals_data
    )
# =========================================================
# INSIGHTS
# =========================================================

@app.route("/insights")
def insights():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    insight_type = request.args.get(
        "type",
        "predictions"
    ).lower()

    allowed_types = [
        "predictions",
        "wellness",
        "sleep",
        "stress",
        "screen",
        "exercise",
        "energy"
    ]

    if insight_type not in allowed_types:

        insight_type = "predictions"

    user_id = session["user_id"]

    conn = get_db_connection()

    predictions = conn.execute(
        """
        SELECT *
        FROM mood_predictions
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    goals = conn.execute(
        """
        SELECT *
        FROM wellness_goals
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.close()

    total = len(
        predictions
    )

    # =================================================
    # DEFAULTS
    # =================================================

    average = 0

    title = "Prediction Insights"

    icon = "📊"

    unit = ""

    status = "No data yet"

    description = ""

    recommendation = ""

    # =================================================
    # PREDICTIONS
    # =================================================

    if insight_type == "predictions":

        title = "Prediction Insights"

        icon = "📊"

        average = total

        unit = " predictions"

        if total == 0:

            status = "No predictions yet"

            description = (
                "Your prediction history will appear here "
                "after you complete your first wellness prediction."
            )

            recommendation = (
                "Start by entering your daily wellness information."
            )

        else:

            status = "Active"

            description = (
                f"You have completed {total} wellness prediction"
                f"{'s' if total != 1 else ''}. "
                "Your prediction history helps track changes "
                "in your wellness patterns over time."
            )

            recommendation = (
                "Continue making predictions regularly to build "
                "a useful personal wellness history."
            )

    # =================================================
    # WELLNESS
    # =================================================

    elif insight_type == "wellness":

        title = "Wellness Insights"

        icon = "💚"

        unit = "/100"

        if total > 0:

            average = round(
                sum(
                    p["wellness_score"]
                    for p in predictions
                ) / total,
                1
            )

            if average >= 80:

                status = "Excellent"

                recommendation = (
                    "Your average wellness score is strong. "
                    "Continue maintaining balanced sleep, activity, "
                    "stress management, screen time, and energy levels."
                )

            elif average >= 60:

                status = "Good"

                recommendation = (
                    "Your wellness is fairly balanced. "
                    "Focus on improving the areas with lower scores."
                )

            elif average >= 40:

                status = "Needs Attention"

                recommendation = (
                    "Consider improving sleep, physical activity, "
                    "stress management, and screen-time habits."
                )

            else:

                status = "Needs Improvement"

                recommendation = (
                    "Try making small, consistent lifestyle improvements "
                    "and monitor your wellness score regularly."
                )

            description = (
                "Your wellness score combines sleep, stress, screen time, "
                "exercise, and energy-level information into a score out of 100."
            )

        else:

            status = "No data"

            description = (
                "Complete a prediction to calculate your wellness score."
            )

            recommendation = (
                "Make your first wellness prediction."
            )

    # =================================================
    # SLEEP
    # =================================================

    elif insight_type == "sleep":

        title = "Sleep Analysis"

        icon = "😴"

        unit = " hours"

        if total > 0:

            average = round(
                sum(
                    p["sleep_hours"]
                    for p in predictions
                ) / total,
                1
            )

            if average < 7:

                status = "Below Recommended Range"

                recommendation = (
                    "Try gradually increasing your sleep duration. "
                    "A consistent sleep routine can support daily energy "
                    "and overall wellness."
                )

            elif average <= 9:

                status = "Healthy Range"

                recommendation = (
                    "Your average sleep is within a generally healthy range. "
                    "Continue maintaining a consistent sleep schedule."
                )

            else:

                status = "Above Typical Range"

                recommendation = (
                    "You are averaging more than 9 hours. "
                    "Focus on consistent sleep timing and monitor how "
                    "you feel during the day."
                )

            description = (
                "This analysis shows your average recorded sleep duration "
                "across your wellness predictions."
            )

        else:

            status = "No data"

            description = (
                "Complete a prediction to analyze your sleep pattern."
            )

            recommendation = (
                "Start recording your daily sleep duration."
            )

    # =================================================
    # STRESS
    # =================================================

    elif insight_type == "stress":

        title = "Stress Analysis"

        icon = "🧘"

        unit = "/10"

        if total > 0:

            average = round(
                sum(
                    p["stress_level"]
                    for p in predictions
                ) / total,
                1
            )

            if average <= 3:

                status = "Low Stress"

                recommendation = (
                    "Your average stress level is relatively low. "
                    "Continue using healthy coping and relaxation habits."
                )

            elif average <= 6:

                status = "Moderate Stress"

                recommendation = (
                    "Your stress level is moderate. "
                    "Try regular breaks, breathing exercises, physical "
                    "activity, and sufficient rest."
                )

            else:

                status = "High Stress"

                recommendation = (
                    "Your average stress level is high. "
                    "Consider relaxation activities and talking to someone "
                    "you trust if stress continues."
                )

            description = (
                "Stress is recorded on a scale from 1 to 10. "
                "Lower values indicate lower recorded stress."
            )

        else:

            status = "No data"

            description = (
                "Complete a prediction to analyze your stress level."
            )

            recommendation = (
                "Start recording your daily stress level."
            )

    # =================================================
    # SCREEN TIME
    # =================================================

    elif insight_type == "screen":

        title = "Screen Time Analysis"

        icon = "📱"

        unit = " hours"

        if total > 0:

            average = round(
                sum(
                    p["screen_time"]
                    for p in predictions
                ) / total,
                1
            )

            target = 5

            if goals:

                target = goals[
                    "screen_time_goal"
                ]

            if average <= target:

                status = "Within Goal"

                recommendation = (
                    f"Your average screen time is within your "
                    f"{target}-hour goal. Continue taking regular screen breaks."
                )

            else:

                status = "Above Goal"

                recommendation = (
                    f"Your average screen time is above your "
                    f"{target}-hour goal. Try reducing unnecessary "
                    "screen use and taking regular breaks."
                )

            description = (
                "This analysis tracks your average recorded daily screen time."
            )

        else:

            status = "No data"

            description = (
                "Complete a prediction to analyze your screen time."
            )

            recommendation = (
                "Start recording your daily screen time."
            )

    # =================================================
    # EXERCISE
    # =================================================

    elif insight_type == "exercise":

        title = "Exercise Analysis"

        icon = "🏃"

        unit = " minutes"

        if total > 0:

            average = round(
                sum(
                    p["exercise_minutes"]
                    for p in predictions
                ) / total,
                1
            )

            target = 30

            if goals:

                target = goals[
                    "exercise_goal"
                ]

            if average >= target:

                status = "Goal Achieved"

                recommendation = (
                    f"Your average exercise time is meeting your "
                    f"{target}-minute goal. Keep maintaining regular activity."
                )

            else:

                status = "Below Goal"

                recommendation = (
                    f"Your average exercise time is below your "
                    f"{target}-minute goal. Try adding walking, stretching, "
                    "or another enjoyable physical activity."
                )

            description = (
                "This analysis shows your average exercise duration "
                "across your recorded predictions."
            )

        else:

            status = "No data"

            description = (
                "Complete a prediction to analyze your exercise activity."
            )

            recommendation = (
                "Start recording your daily exercise duration."
            )

    # =================================================
    # ENERGY
    # =================================================

    elif insight_type == "energy":

        title = "Energy Analysis"

        icon = "⚡"

        unit = "/10"

        energy_values = [
            p["energy_level"]
            for p in predictions
            if p["energy_level"] is not None
        ]

        if energy_values:

            average = round(
                sum(energy_values)
                / len(energy_values),
                1
            )

            target = 7

            if goals:

                target = goals[
                    "energy_goal"
                ]

            if average >= target:

                status = "Goal Achieved"

                recommendation = (
                    f"Your average energy level is meeting "
                    f"your {target}/10 target. Continue maintaining "
                    "balanced sleep, exercise, hydration, and daily routines."
                )

            elif average >= 5:

                status = "Moderate Energy"

                recommendation = (
                    "Your energy level is moderate. Focus on regular "
                    "sleep, physical activity, hydration, and balanced routines."
                )

            else:

                status = "Low Energy"

                recommendation = (
                    "Your average energy level is low. Focus on adequate "
                    "rest, hydration, nutrition, and regular daily routines."
                )

            description = (
                "This analysis shows your average recorded energy level "
                "across your wellness predictions."
            )

        else:

            status = "No data"

            description = (
                "Complete a prediction to analyze your energy level."
            )

            recommendation = (
                "Start recording your daily energy level."
            )

    # =================================================
    # TREND DATA
    # =================================================

    trend_labels = []

    trend_values = []

    for p in reversed(predictions):

        label = (
            f"{p['prediction_date']} "
            f"{p['prediction_time'] or ''}"
        )

        trend_labels.append(
            label
        )

        if insight_type == "wellness":

            value = p[
                "wellness_score"
            ]

        elif insight_type == "sleep":

            value = p[
                "sleep_hours"
            ]

        elif insight_type == "stress":

            value = p[
                "stress_level"
            ]

        elif insight_type == "screen":

            value = p[
                "screen_time"
            ]

        elif insight_type == "exercise":

            value = p[
                "exercise_minutes"
            ]

        elif insight_type == "energy":

            value = (
                p["energy_level"]
                if p["energy_level"] is not None
                else 0
            )

        else:

            value = p[
                "wellness_score"
            ]

        trend_values.append(
            value
        )

    return render_template(
        "insights.html",
        title=title,
        icon=icon,
        average=average,
        unit=unit,
        status=status,
        description=description,
        recommendation=recommendation,
        insight_type=insight_type,
        predictions=predictions,
        trend_labels=trend_labels,
        trend_values=trend_values
    )


# =========================================================
# RUN APP
# =========================================================

if __name__ == "__main__":

    app.run(
    host="0.0.0.0",
    port=5000,
    debug=False
)