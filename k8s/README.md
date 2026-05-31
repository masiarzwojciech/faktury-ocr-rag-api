# Wdrożenie na Kubernetes (Minikube)

## Wymagania
- Docker Desktop
- Minikube: `winget install Kubernetes.minikube`
- kubectl (zainstalowany z Docker Desktop)

## Przygotowanie

### 1. Zakoduj klucz Groq API do base64
W PowerShell:
```powershell
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("twoj_klucz_groq"))
```
Wstaw wynik do `k8s/secret.yaml` w pole `groq-api-key`.

### 2. Zbuduj obraz API
```powershell
docker compose build
```

## Uruchomienie

### 1. Uruchom Minikube
```powershell
minikube start --driver=docker
```

### 2. Załaduj obraz do Minikube
```powershell
minikube image load faktury-api:latest
```

### 3. Wdróż manifesty
```powershell
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/qdrant-deployment.yaml
kubectl apply -f k8s/qdrant-service.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml
```

### 4. Sprawdź status podów
```powershell
kubectl get pods -n faktury
```

Poczekaj aż oba pody mają status `1/1 Running`.

### 5. Udostępnij API
```powershell
minikube service faktury-api-service -n faktury
```

Minikube otworzy przeglądarkę z adresem API.

## Zatrzymanie

```powershell
minikube stop
```

## Usunięcie klastra

```powershell
minikube delete
```

## Architektura
┌─────────────────────────────────────────┐
│           Namespace: faktury            │
│                                         │
│  ┌─────────────────┐                   │
│  │   api-deployment│◄──── NodePort      │
│  │  (faktury-api)  │      :30800        │
│  └────────┬────────┘                   │
│           │ ClusterIP                   │
│  ┌────────▼────────┐                   │
│  │qdrant-deployment│                   │
│  │    (Qdrant)     │                   │
│  └─────────────────┘                   │
│                                         │
│  ┌──────────────┐  ┌────────────────┐  │
│  │   ConfigMap  │  │     Secret     │  │
│  │(konfiguracja)│  │  (klucz API)   │  │
│  └──────────────┘  └────────────────┘  │
└─────────────────────────────────────────┘

## Zasoby Kubernetes

| Zasób | Nazwa | Opis |
|---|---|---|
| Namespace | faktury | Izolowana przestrzeń dla projektu |
| Deployment | api-deployment | Pod z aplikacją FastAPI |
| Deployment | qdrant-deployment | Pod z bazą wektorową Qdrant |
| Service | faktury-api-service | NodePort — dostęp zewnętrzny |
| Service | qdrant-service | ClusterIP — dostęp wewnętrzny |
| ConfigMap | faktury-config | Zmienne konfiguracyjne |
| Secret | faktury-secret | Klucz API Groq |