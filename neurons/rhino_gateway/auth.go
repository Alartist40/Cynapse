package main

import (
	"bufio"
	"log"
	"os"
)

var keyMap = map[string]bool{}

func loadKeys() {
	f, err := os.Open("keys.txt")
	if err != nil {
		log.Fatal("keys.txt missing")
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		keyMap[sc.Text()] = true
	}
}

func validKey(k string) bool { return keyMap[k] }
