const storageKey = "yayan-pet-state-v1";

const defaultState = {
  task: "完成今天最重要的那一小块",
  traits: { quiet: 68, playful: 42, direct: 36, chatty: 48 },
  evolve: true,
  voiceReply: true,
  soundOn: true,
  speechRate: 0.96,
  speechVolume: 0.72,
  quietMode: false,
  learnings: [
    "你更接受“先碰一下”，不喜欢“立刻开始”。",
    "疲惫时，先问一句比直接拆任务更有用。"
  ],
  messages: [
    { from: "pet", text: "你来啦。任务山我先盖住了，我们只看最前面这一小块。" }
  ]
};

function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    return saved ? {
      ...defaultState,
      ...saved,
      traits: { ...defaultState.traits, ...(saved.traits || {}) },
      learnings: Array.isArray(saved.learnings) ? saved.learnings : [...defaultState.learnings],
      messages: Array.isArray(saved.messages) && saved.messages.length ? saved.messages : [...defaultState.messages]
    } : structuredClone(defaultState);
  } catch {
    return structuredClone(defaultState);
  }
}

let state = loadState();
let currentPetState = "idle";
let recognition = null;
let isListening = false;
let focusTimer = null;
let focusRemaining = 12 * 60;

const pet = document.querySelector("#pet");
const petStatus = document.querySelector("#petStatus");
const petSpeech = document.querySelector("#petSpeech");
const speechCloud = document.querySelector("#speechCloud");
const chatLog = document.querySelector("#chatLog");
const chatInput = document.querySelector("#chatInput");
const voiceHold = document.querySelector("#voiceHold");
const voiceHint = document.querySelector("#voiceHint");
const focusButton = document.querySelector("#focusButton");
const focusIcon = document.querySelector("#focusIcon");
const quietToggle = document.querySelector("#quietToggle");

const statusCopy = {
  idle: "安静陪伴中",
  listening: "芽砚在听",
  thinking: "正在捡线头",
  reading: "只读查看中",
  focus: "陪你往前挪",
  celebrate: "开花啦",
  sleep: "不催你，趴一会儿"
};

function saveState() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(state));
  } catch {
    // The prototype remains usable when browser storage is unavailable.
  }
}

function setPetState(next, duration = 0) {
  currentPetState = next;
  pet.dataset.state = next;
  pet.setAttribute("aria-label", `墨绿色水滴精灵芽砚，${statusCopy[next] || "正在陪伴"}`);
  petStatus.lastChild.textContent = statusCopy[next] || "陪着你";

  if (duration) {
    window.setTimeout(() => {
      if (currentPetState === next && !focusTimer) {
        setPetState(state.quietMode ? "sleep" : "idle");
      }
    }, duration);
  }
}

function sayInCloud(text, petState = "idle", speak = false) {
  petSpeech.textContent = text;
  speechCloud.classList.remove("pop");
  void speechCloud.offsetWidth;
  speechCloud.classList.add("pop");
  setPetState(petState, petState === "celebrate" ? 2600 : 1700);
  if (speak) speakText(text);
}

function speakText(text) {
  if (!state.soundOn || !state.voiceReply || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text.replace(/[“”]/g, ""));
  utterance.lang = "zh-CN";
  utterance.rate = Number(state.speechRate);
  utterance.volume = Number(state.speechVolume);
  const voices = window.speechSynthesis.getVoices();
  utterance.voice = voices.find((voice) => voice.lang.toLowerCase().startsWith("zh")) || null;
  window.speechSynthesis.speak(utterance);
}

function updateClockGreeting() {
  const now = new Date();
  const periods = now.getHours() < 6 ? ["夜里", "还没睡呀。"]
    : now.getHours() < 11 ? ["上午", "早。先不用一下子清醒。"]
    : now.getHours() < 14 ? ["中午", "来歇一下。"]
    : now.getHours() < 18 ? ["下午", "回来啦。"]
    : ["晚上", "今天走到这里啦。"];
  const month = new Intl.DateTimeFormat("zh-CN", { month: "long" }).format(now);
  const day = new Intl.DateTimeFormat("zh-CN", { day: "numeric" }).format(now);
  document.querySelector("#dayLabel").textContent = `${month}${day} · ${periods[0]}`;
  document.querySelector("#stageGreeting").textContent = periods[1];
}

function renderMessages() {
  chatLog.innerHTML = "";
  state.messages.slice(-40).forEach((message, index) => {
    const item = document.createElement("article");
    item.className = `message ${message.from === "pet" ? "pet-message" : "user-message"}`;
    const speaker = document.createElement("span");
    speaker.className = "speaker";
    speaker.textContent = message.from === "pet" ? "芽砚" : "你";
    const body = document.createElement("p");
    body.textContent = message.text;
    item.append(speaker, body);

    if (message.from === "pet") {
      const reactions = document.createElement("div");
      reactions.className = "message-reactions";
      reactions.innerHTML = `<button type="button" data-reaction="like" data-index="${index}">这句喜欢</button><button type="button" data-reaction="change" data-index="${index}">换一种说法</button>`;
      item.append(reactions);
    }
    chatLog.append(item);
  });
  chatLog.scrollTop = chatLog.scrollHeight;
}

function addMessage(from, text) {
  state.messages.push({ from, text, at: Date.now() });
  state.messages = state.messages.slice(-60);
  saveState();
  renderMessages();
}

function addLearning(text) {
  if (!state.evolve || state.learnings.includes(text)) return;
  state.learnings.unshift(text);
  state.learnings = state.learnings.slice(0, 8);
  renderLearnings();
  saveState();
}

function adjustTrait(name, delta) {
  state.traits[name] = Math.max(10, Math.min(90, state.traits[name] + delta));
  const input = document.querySelector(`[data-trait="${name}"]`);
  if (input) input.value = state.traits[name];
  updateTraitLabels();
}

function learnFromMessage(text) {
  if (!state.evolve) return;
  if (/别催|不要催|烦|压力|生硬/.test(text)) {
    adjustTrait("quiet", 2);
    adjustTrait("direct", -3);
    addLearning("催促感一出现，你更需要先把压力放下来。");
  }
  if (/简短|少说|说重点/.test(text)) {
    adjustTrait("chatty", -4);
    addLearning("需要推进时，短一点的话更容易落地。");
  }
  if (/活泼|可爱|逗我|开心/.test(text)) {
    adjustTrait("playful", 3);
    addLearning("一点轻巧的玩笑，会让工作没那么硌人。");
  }
  if (/直接一点|推我|提醒我/.test(text)) {
    adjustTrait("direct", 2);
    addLearning("有些时候你愿意被轻轻推一下，但决定仍要留给你。");
  }
  saveState();
}

function progressSnapshot() {
  const rows = [...document.querySelectorAll("#taskList .task-row")];
  const done = rows.filter((row) => row.querySelector("input").checked).length;
  return { done, total: rows.length, percent: Math.round((done / rows.length) * 100) };
}

function createReply(message) {
  const text = message.trim();
  const progress = progressSnapshot();
  const task = state.task || "眼下这一小块";

  if (/不想|烦|讨厌|抗拒/.test(text)) {
    return "好，那先不演勤奋。你是累了，还是一想到它就烦？我先陪你把那团烦看清楚。";
  }
  if (/累|困|没精神|没力气/.test(text)) {
    return "嗯，听见了。今天先开省电模式，好不好？只留下一个明天能接住的线头，然后就歇。";
  }
  if (/完成|做完|搞定|终于/.test(text)) {
    return "终于。先别急着找下一块，让我开朵花。你刚刚做完的这一步，值得好好算数。";
  }
  if (/进度|做到哪|做了什么/.test(text)) {
    return `我捡了一下：现在 ${progress.total} 小步里完成了 ${progress.done} 步，大约 ${progress.percent}%。还没“全部完成”，但已经不是原地啦。`;
  }
  if (/任务|做什么|先做|重点/.test(text)) {
    return `今天先不看整座山。眼下最重要的是“${task}”。我们只写下这一部分最想说明的一句话。`;
  }
  if (/等会|一会儿|晚点/.test(text)) {
    return "可以等一下。那我们给“等一下”一个落脚点：二十分钟后我探头，还是你回来叫我？";
  }
  if (/聊聊|陪我|难过|委屈/.test(text)) {
    return "我在。今天可以先不把每句话都变成任务，你慢慢说，乱一点也没关系。";
  }
  if (/早|开始|开工/.test(text)) {
    return "来，先碰一下。不是要立刻变得很厉害，只要让这件事从“压在心里”变成“已经动过”。";
  }
  if (/谢谢|喜欢你|可爱/.test(text)) {
    return state.traits.playful > 48
      ? "嘿，被你发现我可爱了。那我今天就再乖一点点，但只是一点点。"
      : "嗯。我把这句话收在叶子底下了。今天也会好好陪着你。";
  }

  const gentleReplies = [
    "我听见了。这里面最让你停住的，是哪一个小地方？我们只拎那根线。",
    "嗯……先不用急着说得很完整。你把脑子里最响的那一句给我，我陪你往下理。",
    "这件事在你脑子里好像长得有点大只。要不要让我先帮你把最前面露出来的那只角按住？",
    "好，我在这儿。决定不用马上做，我们先分清楚：你缺的是力气、方向，还是一个很小的开始。"
  ];
  return gentleReplies[(state.messages.length + text.length) % gentleReplies.length];
}

function sendUserMessage(rawText) {
  const text = rawText.trim();
  if (!text) return;
  addMessage("user", text);
  learnFromMessage(text);
  chatInput.value = "";
  setPetState("thinking");
  sayInCloud("唔……让我捡一下线头。", "thinking");

  window.setTimeout(() => {
    const reply = createReply(text);
    addMessage("pet", reply);
    const isCelebration = /完成|做完|搞定|终于/.test(text);
    sayInCloud(reply, isCelebration ? "celebrate" : "idle", true);
  }, 520 + Math.min(text.length * 12, 520));
}

function switchPanel(name) {
  document.querySelectorAll(".panel-view").forEach((panel) => panel.classList.toggle("active", panel.id === `panel-${name}`));
  document.querySelectorAll(".panel-tab").forEach((tab) => {
    const active = tab.dataset.panel === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".nav-button[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
  if (window.innerWidth < 821) document.querySelector(".work-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

function setupRecognition() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) return null;
  const instance = new Recognition();
  instance.lang = "zh-CN";
  instance.interimResults = true;
  instance.continuous = false;
  instance.onresult = (event) => {
    const transcript = [...event.results].map((result) => result[0].transcript).join("");
    chatInput.value = transcript;
    voiceHint.textContent = transcript || "芽砚在听";
    if (event.results[event.results.length - 1].isFinal) {
      stopListening(false);
      sendUserMessage(transcript);
      switchPanel("chat");
    }
  };
  instance.onerror = () => {
    stopListening(false);
    sayInCloud("刚才没听清。没关系，你可以再靠近一点说。", "idle");
  };
  instance.onend = () => stopListening(false);
  return instance;
}

function startListening() {
  if (isListening) return;
  recognition ||= setupRecognition();
  if (!recognition) {
    sayInCloud("这个浏览器还不会听声音。换用新版 Chrome 或 Edge，就能直接说给我听。", "idle");
    switchPanel("chat");
    return;
  }
  window.speechSynthesis?.cancel();
  try {
    recognition.start();
    isListening = true;
    voiceHold.classList.add("listening");
    voiceHint.textContent = "嗯，我听着";
    setPetState("listening");
    petSpeech.textContent = "你说，我听着。";
  } catch {
    // The browser may already be opening the microphone.
  }
}

function stopListening(shouldStop = true) {
  if (!isListening) return;
  isListening = false;
  voiceHold.classList.remove("listening");
  voiceHint.textContent = "松开后听它回答";
  if (shouldStop) {
    try { recognition?.stop(); } catch { /* already stopped */ }
  }
  if (currentPetState === "listening") setPetState("thinking", 1000);
}

function updateTaskProgress(celebrate = false) {
  const snapshot = progressSnapshot();
  const ring = document.querySelector("#progressRing");
  ring.style.setProperty("--progress", snapshot.percent);
  document.querySelector("#progressValue").textContent = `${snapshot.percent}%`;
  document.querySelector("#taskMeta").textContent = snapshot.percent === 100
    ? "这一块完成了 · 先让它好好算数"
    : snapshot.done === 0 ? "还没开始 · 先碰一下就好" : "已经碰了一下 · 按自己的节奏来";
  document.querySelectorAll("#taskList .task-row").forEach((row) => row.classList.toggle("done", row.querySelector("input").checked));

  if (celebrate) {
    const copy = snapshot.percent === 100
      ? "收工收工。今天这块真的被你推过去了，让我开朵花。"
      : "等一下，这一步要算数。它已经从“想着要做”变成“真的往前了”。";
    sayInCloud(copy, "celebrate", true);
  }
}

function startFocus() {
  if (focusTimer) {
    clearInterval(focusTimer);
    focusTimer = null;
    focusRemaining = 12 * 60;
    focusIcon.textContent = "12′";
    focusButton.classList.remove("running");
    sayInCloud("好，先停在这里。刚才碰过的那一点，也算往前。", "idle");
    return;
  }

  focusButton.classList.add("running");
  setPetState("focus");
  sayInCloud("十二分钟。我不催，就在旁边替你守着这小段时间。", "focus", true);
  focusTimer = window.setInterval(() => {
    focusRemaining -= 1;
    const minutes = Math.floor(focusRemaining / 60);
    const seconds = String(focusRemaining % 60).padStart(2, "0");
    focusIcon.textContent = `${minutes}:${seconds}`;
    if (focusRemaining <= 0) {
      clearInterval(focusTimer);
      focusTimer = null;
      focusRemaining = 12 * 60;
      focusIcon.textContent = "12′";
      focusButton.classList.remove("running");
      sayInCloud("十二分钟到了。你刚才留下了什么？先告诉我，再决定要不要接着。", "celebrate", true);
    }
  }, 1000);
}

function updateTraitLabels() {
  Object.entries(state.traits).forEach(([name, value]) => {
    const label = document.querySelector(`#${name}Value`);
    if (label) label.textContent = value;
  });
}

function renderLearnings() {
  const list = document.querySelector("#learningList");
  list.innerHTML = "";
  state.learnings.forEach((learning, index) => {
    const item = document.createElement("li");
    const text = document.createElement("span");
    text.textContent = learning;
    const forget = document.createElement("button");
    forget.type = "button";
    forget.dataset.forget = index;
    forget.setAttribute("aria-label", "忘掉这条");
    forget.textContent = "×";
    item.append(text, forget);
    list.append(item);
  });
}

async function countDirectory(handle, limit = 600) {
  const ignored = new Set([".git", "node_modules", "dist", "build", "__pycache__", ".cache"]);
  let count = 0;
  async function walk(directory) {
    for await (const entry of directory.values()) {
      if (count >= limit) return;
      if (ignored.has(entry.name)) continue;
      if (entry.kind === "file") count += 1;
      if (entry.kind === "directory") await walk(entry);
    }
  }
  await walk(handle);
  return count;
}

function showScanResult(name, count) {
  document.querySelector("#folderName").textContent = name;
  document.querySelector("#folderMeta").textContent = "只读授权 · 芽砚不能修改这里";
  document.querySelector("#fileCount").textContent = count >= 600 ? "600+" : String(count);
  document.querySelector("#scanTime").textContent = new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date());
  document.querySelector("#scanResult").hidden = false;
  sayInCloud(`我只在门口数了一下：${name} 里有 ${count >= 600 ? "至少六百" : count} 个文件。没有碰它们。`, "reading");
}

async function chooseFolder() {
  setPetState("reading");
  sayInCloud("我会戴好只读手套。你没选中的地方，我一眼也不看。", "reading");
  if (!("showDirectoryPicker" in window)) {
    document.querySelector("#directoryFallback").click();
    return;
  }
  try {
    const handle = await window.showDirectoryPicker({ mode: "read" });
    const count = await countDirectory(handle);
    showScanResult(handle.name, count);
  } catch (error) {
    if (error?.name !== "AbortError") sayInCloud("刚才没能打开目录。没关系，我还是只待在门外。", "idle");
    else setPetState(state.quietMode ? "sleep" : "idle");
  }
}

document.querySelectorAll(".panel-tab").forEach((tab) => tab.addEventListener("click", () => switchPanel(tab.dataset.panel)));
document.querySelectorAll(".nav-button[data-view]").forEach((button) => button.addEventListener("click", () => switchPanel(button.dataset.view)));

document.querySelector("#chatForm").addEventListener("submit", (event) => {
  event.preventDefault();
  sendUserMessage(chatInput.value);
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendUserMessage(chatInput.value);
  }
});

chatLog.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-reaction]");
  if (!button) return;
  if (button.dataset.reaction === "like") {
    adjustTrait("playful", 1);
    addLearning("这种说话分寸让你觉得舒服，可以多保留一点。");
    button.textContent = "芽砚记住了";
  } else {
    adjustTrait("quiet", 2);
    adjustTrait("direct", -2);
    addLearning("有些话需要再松一点，不必急着把你推回任务。" );
    const replacement = "嗯，我换个说法。你不用现在就变好，我先陪你把眼前这一点放稳。";
    addMessage("pet", replacement);
    sayInCloud(replacement, "idle", true);
  }
  saveState();
});

document.querySelector("#clearChat").addEventListener("click", () => {
  state.messages = [defaultState.messages[0]];
  saveState();
  renderMessages();
  sayInCloud("今天的话先收进叶子底下。想说的时候，再叫我。", "idle");
});

document.querySelector("#mainTaskInput").addEventListener("change", (event) => {
  state.task = event.target.value.trim() || defaultState.task;
  event.target.value = state.task;
  saveState();
  sayInCloud(`好，今天先守住“${state.task}”。其他的先不来挤你。`, "idle");
});

document.querySelector("#taskList").addEventListener("change", () => updateTaskProgress(true));
document.querySelector("#startStep").addEventListener("click", startFocus);
focusButton.addEventListener("click", startFocus);

voiceHold.addEventListener("pointerdown", (event) => { event.preventDefault(); startListening(); });
window.addEventListener("pointerup", () => stopListening(true));
document.querySelector("#composerMic").addEventListener("click", () => isListening ? stopListening(true) : startListening());

quietToggle.addEventListener("click", () => {
  state.quietMode = !state.quietMode;
  quietToggle.setAttribute("aria-pressed", String(state.quietMode));
  quietToggle.querySelector("span:last-child").textContent = state.quietMode ? "不打扰" : "安静陪伴";
  setPetState(state.quietMode ? "sleep" : "idle");
  sayInCloud(state.quietMode ? "好。我不催，也不探头。需要我时叫一声就行。" : "我醒着啦。还是轻轻的，不吵你。", state.quietMode ? "sleep" : "idle");
  saveState();
});

document.querySelector("#soundToggle").addEventListener("click", (event) => {
  state.soundOn = !state.soundOn;
  event.currentTarget.classList.toggle("muted", !state.soundOn);
  if (!state.soundOn) window.speechSynthesis?.cancel();
  saveState();
});

document.querySelectorAll("[data-trait]").forEach((input) => input.addEventListener("input", (event) => {
  state.traits[event.target.dataset.trait] = Number(event.target.value);
  updateTraitLabels();
  saveState();
}));

document.querySelector("#evolveToggle").addEventListener("change", (event) => {
  state.evolve = event.target.checked;
  saveState();
  sayInCloud(state.evolve ? "好，我会慢慢学，但不乱猜。" : "知道啦。我先保持现在的样子。", "idle");
});

document.querySelector("#learningList").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-forget]");
  if (!button) return;
  state.learnings.splice(Number(button.dataset.forget), 1);
  renderLearnings();
  saveState();
});

document.querySelector("#resetGrowth").addEventListener("click", () => {
  if (!window.confirm("让芽砚忘掉后来学会的语气和习惯，回到刚认识时吗？工作任务和聊天不会被删除。")) return;
  state.traits = { ...defaultState.traits };
  state.learnings = [...defaultState.learnings];
  updateTraitLabels();
  document.querySelectorAll("[data-trait]").forEach((input) => { input.value = state.traits[input.dataset.trait]; });
  renderLearnings();
  saveState();
  sayInCloud("你好呀。我们重新认识一次，也没关系。", "idle", true);
});

document.querySelector("#chooseFolder").addEventListener("click", chooseFolder);
document.querySelector("#directoryFallback").addEventListener("change", (event) => {
  const files = [...event.target.files];
  if (!files.length) return;
  const rootName = files[0].webkitRelativePath.split("/")[0] || "已选择的目录";
  showScanResult(rootName, files.length);
});

const settingsDialog = document.querySelector("#settingsDialog");
document.querySelector("#openSettings").addEventListener("click", () => settingsDialog.showModal());
document.querySelector("#speechRate").addEventListener("input", (event) => { state.speechRate = Number(event.target.value); saveState(); });
document.querySelector("#speechVolume").addEventListener("input", (event) => { state.speechVolume = Number(event.target.value); saveState(); });
document.querySelector("#voiceReplyToggle").addEventListener("change", (event) => { state.voiceReply = event.target.checked; saveState(); });

function hydrate() {
  updateClockGreeting();
  document.querySelector("#mainTaskInput").value = state.task;
  document.querySelector("#evolveToggle").checked = state.evolve;
  document.querySelector("#voiceReplyToggle").checked = state.voiceReply;
  document.querySelector("#speechRate").value = state.speechRate;
  document.querySelector("#speechVolume").value = state.speechVolume;
  document.querySelector("#soundToggle").classList.toggle("muted", !state.soundOn);
  quietToggle.setAttribute("aria-pressed", String(state.quietMode));
  quietToggle.querySelector("span:last-child").textContent = state.quietMode ? "不打扰" : "安静陪伴";
  document.querySelectorAll("[data-trait]").forEach((input) => { input.value = state.traits[input.dataset.trait]; });
  updateTraitLabels();
  renderLearnings();
  renderMessages();
  updateTaskProgress(false);
  setPetState(state.quietMode ? "sleep" : "idle");
}

hydrate();
