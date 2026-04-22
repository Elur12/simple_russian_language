import { useEffect, useState } from "react";
import {
  analyzeText,
  deleteProfileToken,
  fetchUrlText,
  getProfileToken,
  loginUser,
  registerUser,
  saveProfileToken,
  type AnalysisResponse,
  type TokenStatus,
} from "./api/client";
import { TextAnalysisViewer } from "./components/TextAnalysisViewer";

type InputMode = "text" | "url";

export default function App() {
  const [accessToken, setAccessToken] = useState<string>(localStorage.getItem("access_token") || "");
  const [refreshToken, setRefreshToken] = useState<string>(localStorage.getItem("refresh_token") || "");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [inputMode, setInputMode] = useState<InputMode>("text");
  const [text, setText] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [fetchedTitle, setFetchedTitle] = useState<string | null>(null);
  const [fetchedUrl, setFetchedUrl] = useState<string | null>(null);

  const [tokenInput, setTokenInput] = useState("");
  const [tokenStatus, setTokenStatus] = useState<TokenStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchingUrl, setFetchingUrl] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setTokenStatus(null);
      return;
    }
    getProfileToken(accessToken)
      .then(setTokenStatus)
      .catch(() => setTokenStatus(null));
  }, [accessToken]);

  function switchInputMode(mode: InputMode) {
    setInputMode(mode);
    setError(null);
    setResult(null);
    if (mode === "text") {
      setFetchedTitle(null);
      setFetchedUrl(null);
    }
  }

  async function onFetchUrl() {
    const url = urlInput.trim();
    if (!url) {
      setError("Введите ссылку на страницу.");
      return;
    }
    if (!accessToken) {
      setError("Сначала войдите в аккаунт.");
      return;
    }

    setError(null);
    setFetchedTitle(null);
    setFetchedUrl(null);
    setFetchingUrl(true);
    try {
      const data = await fetchUrlText(url, accessToken);
      setText(data.text);
      setFetchedTitle(data.title || null);
      setFetchedUrl(data.url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить страницу.");
    } finally {
      setFetchingUrl(false);
    }
  }

  async function onAnalyze() {
    setError(null);
    setResult(null);

    if (!text.trim()) {
      setError(inputMode === "url" ? "Сначала загрузите текст со страницы." : "Вставьте текст для анализа.");
      return;
    }
    if (!accessToken) {
      setError("Сначала войдите в аккаунт.");
      return;
    }
    if (!tokenStatus?.has_token) {
      setError("Сначала сохраните токен Yandex AI Studio в профиле.");
      return;
    }

    setLoading(true);
    try {
      const data = await analyzeText(text, accessToken);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Неизвестная ошибка");
    } finally {
      setLoading(false);
    }
  }

  async function onAuthSubmit() {
    setError(null);
    try {
      if (authMode === "register") {
        await registerUser({ username, email, password });
      }
      const tokens = await loginUser({ username, password });
      setAccessToken(tokens.access);
      setRefreshToken(tokens.refresh);
      localStorage.setItem("access_token", tokens.access);
      localStorage.setItem("refresh_token", tokens.refresh);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка авторизации");
    }
  }

  async function onSaveApiToken() {
    if (!accessToken) { setError("Сначала войдите в аккаунт."); return; }
    if (!tokenInput.trim()) { setError("Введите токен Yandex AI Studio."); return; }
    setError(null);
    try {
      const status = await saveProfileToken(accessToken, tokenInput.trim());
      setTokenStatus(status);
      setTokenInput("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения токена");
    }
  }

  async function onDeleteApiToken() {
    if (!accessToken) { setError("Сначала войдите в аккаунт."); return; }
    setError(null);
    try {
      await deleteProfileToken(accessToken);
      setTokenStatus({ has_token: false });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка удаления токена");
    }
  }

  function onLogout() {
    setAccessToken("");
    setRefreshToken("");
    setTokenStatus(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  return (
    <main className="page">
      <section className="panel">
        <h1>Проверка на Простой язык</h1>
        <p>Вставьте текст или укажите ссылку на страницу — получите разметку по абзацам с советами по исправлению.</p>

        {!accessToken ? (
          <>
            <div className="auth-switch">
              <button type="button" onClick={() => setAuthMode("login")}>Вход</button>
              <button type="button" onClick={() => setAuthMode("register")}>Регистрация</button>
            </div>

            <label>Логин</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" />

            {authMode === "register" && (
              <>
                <label>Email</label>
                <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@example.com" />
              </>
            )}

            <label>Пароль</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Минимум 8 символов" />

            <button type="button" onClick={onAuthSubmit}>
              {authMode === "login" ? "Войти" : "Зарегистрироваться"}
            </button>
          </>
        ) : (
          <>
            <p>Вы авторизованы. Refresh token сохранен локально: {refreshToken ? "да" : "нет"}.</p>
            <button type="button" onClick={onLogout}>Выйти</button>

            <label>Токен Yandex AI Studio</label>
            <input
              type="password"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="Введите токен и нажмите Сохранить"
            />
            <div className="token-row">
              <button type="button" onClick={onSaveApiToken}>Сохранить токен</button>
              <button type="button" onClick={onDeleteApiToken}>Удалить токен</button>
            </div>
            <p>Статус токена: {tokenStatus?.has_token ? `сохранен (${tokenStatus.masked_token || "***"})` : "не сохранен"}</p>
          </>
        )}

        {/* Input mode toggle */}
        <div className="input-mode-toggle">
          <button
            type="button"
            className={`mode-btn ${inputMode === "text" ? "mode-btn-active" : ""}`}
            onClick={() => switchInputMode("text")}
          >
            ✏️ Текст
          </button>
          <button
            type="button"
            className={`mode-btn ${inputMode === "url" ? "mode-btn-active" : ""}`}
            onClick={() => switchInputMode("url")}
          >
            🔗 Ссылка на страницу
          </button>
        </div>

        {/* URL input */}
        {inputMode === "url" && (
          <div className="url-input-area">
            <label>Ссылка на страницу</label>
            <div className="url-row">
              <input
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://example.com/article"
                onKeyDown={(e) => e.key === "Enter" && onFetchUrl()}
              />
              <button type="button" onClick={onFetchUrl} disabled={fetchingUrl} className="btn-fetch">
                {fetchingUrl ? "..." : "↓ Загрузить"}
              </button>
            </div>
            {fetchedUrl && (
              <div className="fetched-meta">
                {fetchedTitle && <span className="fetched-title">{fetchedTitle}</span>}
                <a href={fetchedUrl} target="_blank" rel="noopener noreferrer" className="fetched-link">
                  {fetchedUrl}
                </a>
              </div>
            )}
          </div>
        )}

        {/* Text area — shown in text mode always, in url mode after fetch */}
        {(inputMode === "text" || fetchedUrl) && (
          <>
            <label>{inputMode === "url" ? "Извлечённый текст (можно отредактировать)" : "Текст"}</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={10}
              placeholder={inputMode === "url" ? "Текст появится после загрузки страницы" : "Вставьте текст для анализа"}
            />
          </>
        )}

        <button disabled={loading || fetchingUrl} onClick={onAnalyze}>
          {loading ? "Анализируем..." : "Запустить анализ"}
        </button>

        {error && <p className="error">{error}</p>}
      </section>

      {result && (
        <TextAnalysisViewer
          analysisResult={result}
          originalText={text}
          sourceTitle={fetchedTitle}
          sourceUrl={fetchedUrl}
        />
      )}
    </main>
  );
}
