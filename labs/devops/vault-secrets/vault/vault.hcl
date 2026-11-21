# Serveur Vault de lab : stockage fichier, HTTP sans TLS (réseau du lab uniquement).
ui            = true
disable_mlock = true
api_addr      = "http://vault:8200"

storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}
