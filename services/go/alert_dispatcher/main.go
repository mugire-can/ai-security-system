package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"net/smtp"
	"os"
	"sync"
	"time"
)

type Alert struct {
	CameraID    string    `json:"camera_id"`
	Zone        string    `json:"zone"`
	AlertType   string    `json:"alert_type"`
	Severity    string    `json:"severity"`
	Description string    `json:"description"`
	Timestamp   time.Time `json:"timestamp"`
}

type AlertDispatcher struct {
	smtpHost    string
	smtpPort    string
	smtpUser    string
	smtpPass    string
	webhookURL  string
	adminEmail  string
	alertQueue  chan Alert
	cooldown    map[string]time.Time
	cooldownMu  sync.RWMutex
	cooldownSec int
}

func NewAlertDispatcher(smtpHost, smtpPort, smtpUser, smtpPass, webhookURL, adminEmail string, cooldownSec int) *AlertDispatcher {
	return &AlertDispatcher{
		smtpHost:    smtpHost,
		smtpPort:    smtpPort,
		smtpUser:    smtpUser,
		smtpPass:    smtpPass,
		webhookURL:  webhookURL,
		adminEmail:  adminEmail,
		alertQueue:  make(chan Alert, 100),
		cooldown:    make(map[string]time.Time),
		cooldownSec: cooldownSec,
	}
}

func (ad *AlertDispatcher) isRateLimited(key string) bool {
	ad.cooldownMu.RLock()
	lastTime, exists := ad.cooldown[key]
	ad.cooldownMu.RUnlock()

	if !exists {
		return false
	}

	if time.Since(lastTime) < time.Duration(ad.cooldownSec)*time.Second {
		return true
	}

	ad.cooldownMu.Lock()
	delete(ad.cooldown, key)
	ad.cooldownMu.Unlock()
	return false
}

func (ad *AlertDispatcher) updateCooldown(key string) {
	ad.cooldownMu.Lock()
	defer ad.cooldownMu.Unlock()
	ad.cooldown[key] = time.Now()
}

func (ad *AlertDispatcher) SendEmail(alert Alert) error {
	from := ad.smtpUser
	to := []string{ad.adminEmail}

	subject := fmt.Sprintf("[%s] Security Alert: %s", alert.Severity, alert.AlertType)
	body := fmt.Sprintf(
		"Camera: %s\nZone: %s\nAlert Type: %s\nSeverity: %s\nDescription: %s\nTime: %s",
		alert.CameraID, alert.Zone, alert.AlertType, alert.Severity, alert.Description, alert.Timestamp.Format(time.RFC3339),
	)

	msg := fmt.Sprintf("Subject: %s\r\n\r\n%s", subject, body)

	auth := smtp.PlainAuth("", from, ad.smtpPass, ad.smtpHost)
	addr := fmt.Sprintf("%s:%s", ad.smtpHost, ad.smtpPort)

	err := smtp.SendMail(addr, auth, from, to, []byte(msg))
	if err != nil {
		log.Printf("Failed to send email: %v", err)
		return err
	}

	log.Printf("Email sent for alert: %s", alert.AlertType)
	return nil
}

func (ad *AlertDispatcher) SendWebhook(alert Alert) error {
	payload, err := json.Marshal(alert)
	if err != nil {
		return err
	}

	resp, err := http.Post(ad.webhookURL, "application/json", bytes.NewBuffer(payload))
	if err != nil {
		log.Printf("Failed to send webhook: %v", err)
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		log.Printf("Webhook returned status %d", resp.StatusCode)
		return fmt.Errorf("webhook failed with status %d", resp.StatusCode)
	}

	log.Printf("Webhook sent for alert: %s", alert.AlertType)
	return nil
}

func (ad *AlertDispatcher) ProcessAlert(alert Alert) {
	key := fmt.Sprintf("%s:%s:%s", alert.CameraID, alert.Zone, alert.AlertType)

	if ad.isRateLimited(key) {
		log.Printf("Alert rate-limited: %s", key)
		return
	}

	ad.updateCooldown(key)

	if ad.adminEmail != "" {
		if err := ad.SendEmail(alert); err != nil {
			log.Printf("Email error: %v", err)
		}
	}

	if ad.webhookURL != "" {
		if err := ad.SendWebhook(alert); err != nil {
			log.Printf("Webhook error: %v", err)
		}
	}
}

func (ad *AlertDispatcher) Start(workers int) {
	for i := 0; i < workers; i++ {
		go ad.worker()
	}
	log.Printf("Alert dispatcher started with %d workers", workers)
}

func (ad *AlertDispatcher) worker() {
	for alert := range ad.alertQueue {
		ad.ProcessAlert(alert)
	}
}

func (ad *AlertDispatcher) QueueAlert(alert Alert) {
	select {
	case ad.alertQueue <- alert:
		log.Printf("Alert queued: %s", alert.AlertType)
	default:
		log.Printf("Alert queue full, dropping: %s", alert.AlertType)
	}
}

func main() {
	port := flag.String("port", "8080", "HTTP server port")
	smtpHost := flag.String("smtp-host", os.Getenv("SMTP_HOST"), "SMTP host")
	smtpPort := flag.String("smtp-port", "587", "SMTP port")
	smtpUser := flag.String("smtp-user", os.Getenv("SMTP_USER"), "SMTP user")
	smtpPass := flag.String("smtp-pass", os.Getenv("SMTP_PASSWORD"), "SMTP password")
	webhookURL := flag.String("webhook-url", os.Getenv("ALERT_WEBHOOK_URL"), "Webhook URL")
	adminEmail := flag.String("admin-email", os.Getenv("ADMIN_EMAIL"), "Admin email")
	cooldown := flag.Int("cooldown", 60, "Cooldown seconds between alerts")
	flag.Parse()

	dispatcher := NewAlertDispatcher(*smtpHost, *smtpPort, *smtpUser, *smtpPass, *webhookURL, *adminEmail, *cooldown)
	dispatcher.Start(4)

	http.HandleFunc("/alert", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
			return
		}

		var alert Alert
		if err := json.NewDecoder(r.Body).Decode(&alert); err != nil {
			http.Error(w, "Invalid alert JSON", http.StatusBadRequest)
			return
		}

		alert.Timestamp = time.Now()
		dispatcher.QueueAlert(alert)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "queued"})
	})

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "healthy"})
	})

	log.Printf("Alert dispatcher listening on :%s", *port)
	if err := http.ListenAndServe(":"+*port, nil); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
