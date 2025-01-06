import openai

# Set your OpenAI API key
openai.api_key = "your-api-key-here"

#get message of user and return corresponding response
def get_response(user_input: str)->str:
    user_input = user_input.lower()
    print("user sent a message")    
    if user_input == '':
        return "????"
    elif "hello" in user_input:
        return 'Hello there'
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Model to use
            messages=[{"role": "user", "content": user_input}],  # ChatGPT expects a conversation-like structure
            max_tokens=100,  # Limit the response tokens
            temperature=0.7,  # Control randomness (0.7 is a good starting point)
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"An error occurred: {e}"

# response = get_response(x)
# print(response)

