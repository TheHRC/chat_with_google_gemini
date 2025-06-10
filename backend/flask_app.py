from chatbot_helpers import chatbot
from langchain_llm import llm_initializer
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Flask app & socket setup
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# DB Setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
db = SQLAlchemy(app)

# Embeddings path
embeddings_path = input("Enter the embedding's path: ").strip()
llm = llm_initializer(embeddings_path)


# Define User and Message models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)


with app.app_context():
    db.create_all()


@app.get("/")
def index():
    render_template("index.html")


@socketio.on('message')
def handle_message(message):
    print(message)
    # print(f"message: {message}")
    # response = chatbot(message)

    # Google gemini
    response = llm.ask_llm(message)
    print(f"res====================")
    print(response)
    socketio.emit('response', response)


@app.route('/set_username', methods=['POST'])
def set_username():
    data = request.get_json()
    username = data.get('username')

    user = User.query.filter_by(username=username).first()

    if user is None:
        new_user = User(username=username)
        db.session.add(new_user)
        db.session.commit()
        print("saved")
        return jsonify({'success': True})
    else:
        print("already exist")
        return jsonify({'success': False, 'message': 'Username already taken'})


if __name__ == '__main__':
    # socketio.run(app, host="192.168.1.4", port=5000)
    socketio.run(app, port=5000)

