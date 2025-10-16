from flask import Flask, render_template, request, jsonify
from chatbot_logic import ask_nova
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        user_message = data.get('message', '')

        if not user_message.strip():
            return jsonify({'reply': "Please enter a message."})

        response = ask_nova(user_message)
        return jsonify({'reply': response})

    except Exception as e:
        print("Error:", e)
        return jsonify({'reply': "⚠️ Sorry, something went wrong on Nova's side."})

if __name__ == '__main__':
    app.run(debug=True)
