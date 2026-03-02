package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"
)

type CameraStream struct {
	CameraID string
	Source   string
	LastSeen time.Time
	mu       sync.RWMutex
}

type StreamManager struct {
	streams map[string]*CameraStream
	mu      sync.RWMutex
}

func NewStreamManager() *StreamManager {
	return &StreamManager{
		streams: make(map[string]*CameraStream),
	}
}

func (sm *StreamManager) RegisterCamera(cameraID, source string) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	sm.streams[cameraID] = &CameraStream{
		CameraID: cameraID,
		Source:   source,
		LastSeen: time.Now(),
	}
	log.Printf("Camera registered: %s -> %s", cameraID, source)
}

func (sm *StreamManager) Heartbeat(cameraID string) error {
	sm.mu.RLock()
	stream, exists := sm.streams[cameraID]
	sm.mu.RUnlock()

	if !exists {
		return fmt.Errorf("camera not found: %s", cameraID)
	}

	stream.mu.Lock()
	defer stream.mu.Unlock()
	stream.LastSeen = time.Now()
	return nil
}

func (sm *StreamManager) GetCameraStatus(cameraID string) (map[string]interface{}, error) {
	sm.mu.RLock()
	stream, exists := sm.streams[cameraID]
	sm.mu.RUnlock()

	if !exists {
		return nil, fmt.Errorf("camera not found: %s", cameraID)
	}

	stream.mu.RLock()
	defer stream.mu.RUnlock()

	isAlive := time.Since(stream.LastSeen) < 30*time.Second

	return map[string]interface{}{
		"camera_id": stream.CameraID,
		"source":    stream.Source,
		"alive":     isAlive,
		"last_seen": stream.LastSeen.Format(time.RFC3339),
	}, nil
}

func (sm *StreamManager) GetAllCameras() []map[string]interface{} {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	var result []map[string]interface{}
	for _, stream := range sm.streams {
		status, _ := sm.GetCameraStatus(stream.CameraID)
		result = append(result, status)
	}
	return result
}

func main() {
	port := flag.String("port", "8081", "HTTP server port")
	flag.Parse()

	manager := NewStreamManager()

	http.HandleFunc("/camera/register", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
			return
		}

		cameraID := r.FormValue("camera_id")
		source := r.FormValue("source")

		if cameraID == "" || source == "" {
			http.Error(w, "Missing camera_id or source", http.StatusBadRequest)
			return
		}

		manager.RegisterCamera(cameraID, source)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status":"registered","camera_id":"%s"}`, cameraID)
	})

	http.HandleFunc("/camera/heartbeat", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
			return
		}

		cameraID := r.FormValue("camera_id")
		if cameraID == "" {
			http.Error(w, "Missing camera_id", http.StatusBadRequest)
			return
		}

		if err := manager.Heartbeat(cameraID); err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status":"alive","camera_id":"%s"}`, cameraID)
	})

	http.HandleFunc("/camera/status", func(w http.ResponseWriter, r *http.Request) {
		cameraID := r.URL.Query().Get("camera_id")
		if cameraID == "" {
			w.Header().Set("Content-Type", "application/json")
			fmt.Fprint(w, "[")
			cameras := manager.GetAllCameras()
			for i, cam := range cameras {
				if i > 0 {
					fmt.Fprint(w, ",")
				}
				fmt.Fprintf(w, `{"camera_id":"%v","source":"%v","alive":%v,"last_seen":"%v"}`,
					cam["camera_id"], cam["source"], cam["alive"], cam["last_seen"])
			}
			fmt.Fprint(w, "]")
			return
		}

		status, err := manager.GetCameraStatus(cameraID)
		if err != nil {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"camera_id":"%v","source":"%v","alive":%v,"last_seen":"%v"}`,
			status["camera_id"], status["source"], status["alive"], status["last_seen"])
	})

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"status":"healthy"}`)
	})

	log.Printf("Camera streamer listening on :%s", *port)
	if err := http.ListenAndServe(":"+*port, nil); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
