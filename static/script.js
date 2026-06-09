function toggleDark(){
    document.body.classList.toggle("dark-mode");
}

function startVoice(){
    if(!('webkitSpeechRecognition' in window)){
        alert("Voice recognition not supported. Use Chrome browser.");
        return;
    }

    let recognition = new webkitSpeechRecognition();
    recognition.lang = "en-IN";
    recognition.start();

    recognition.onstart = function(){
        let voiceText = document.getElementById("voiceText");
        if(voiceText){
            voiceText.innerHTML = "🎤 Listening...";
        }
    }

    recognition.onresult = function(event){
        let text = event.results[0][0].transcript;

        let voiceText = document.getElementById("voiceText");
        if(voiceText){
            voiceText.innerHTML = "🧠 You said: " + text;
        }

        let input = document.querySelector('input[name="message"]');
        if(input){
            input.value = text;
        }

        let speak = new SpeechSynthesisUtterance("I heard " + text);
        speak.rate = 1;
        speak.pitch = 1;
        speechSynthesis.speak(speak);
    }

    recognition.onerror = function(){
        let voiceText = document.getElementById("voiceText");
        if(voiceText){
            voiceText.innerHTML = "❌ Voice recognition failed";
        }
    }
}
