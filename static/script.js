document.getElementById("send-btn").addEventListener("click", sendMessage);
document.getElementById("user-input").addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendMessage();
});

async function sendMessage() {
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const userMessage = input.value.trim();
  if (!userMessage) return;

  // Display user message
  const userDiv = document.createElement("div");
  userDiv.classList.add("user-message");
  userDiv.textContent = userMessage;
  chatBox.appendChild(userDiv);
  input.value = "";

  // Typing animation
  const typingDiv = document.createElement("div");
  typingDiv.classList.add("bot-message");
  typingDiv.innerHTML = "Nova is typing<span class='typing'></span><span class='typing'></span><span class='typing'></span>";
  chatBox.appendChild(typingDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  // Fetch AI response
  const response = await fetch("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: userMessage }),
  });

  const data = await response.json();

  // Replace typing animation with Nova's response
  typingDiv.innerHTML = data.reply;
  chatBox.scrollTop = chatBox.scrollHeight;
}
