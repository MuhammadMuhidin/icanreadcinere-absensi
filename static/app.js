
const publicVapidKey = 'BNc5DdHvGk09W2ebsaLbxljExffW2mKxXMquzjNl1cbnWmrzk1jVvRPXE7AmKlPM0vQCQWJnJXdcoqV08x4QYjc=';

if ('serviceWorker' in navigator && 'PushManager' in window) {
    window.addEventListener('load', () => {
        subscribeUser().catch(err => console.error('Push subscribe failed:', err));
    });
}

async function subscribeUser() {
    console.log("Registering service worker...");
    const register = await navigator.serviceWorker.register('/worker.js', {
        scope: '/'
    });
    console.log("Service worker registered.");

    console.log("Waiting for service worker to become ready...");
    await navigator.serviceWorker.ready;
    console.log("Service worker ready.");

try {
    console.log("Subscribing to push manager...");
    const subscription = await register.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicVapidKey)
    });
    console.log("Subscribed:", subscription);

    console.log("Sending subscription to server...");
    await fetch('/subscribe', {
        method: 'POST',
        body: JSON.stringify(subscription),
        headers: {
            'content-type': 'application/json'
        }
    });
    console.log("Subscription sent to server.");
} catch (err) {
    console.error("Push subscribe failed:", err);
}
}


function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}
