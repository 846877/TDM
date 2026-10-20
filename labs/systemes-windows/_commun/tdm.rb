# Outils communs aux Vagrantfile des labs Windows de TDM (voir ../README.md).
#
#   require_relative "../_commun/tdm"
#   Vagrant.configure("2") do |config|
#     TDM.lab(config, __dir__) do |lab|
#       lab.server "dc01", hostname: "SRV-DC01", ip: "192.168.10.10", domain: :forest, primary: true
#       lab.client "pc01", hostname: "PC01", ip: "192.168.10.101", dns: "192.168.10.10", join: true
#     end
#   end
#
# Chaque VM a deux cartes : « NAT » (celle de Vagrant : WinRM, SSH et RDP redirigés sur 127.0.0.1) et
# « LAN », branchée sur un réseau interne VirtualBox propre au lab (tdm-<lab>), configurée par
# provision/base.ps1 (adresse fixe, ou rien du tout si ip: nil : c'est alors à l'élève de le faire).
# La plateforme se connecte en SSH (OpenSSH Server, shell PowerShell) avec une clé générée pour le lab.

require "base64"
require "fileutils"
require "openssl"

module TDM
  SERVER_BOX = ENV["TDM_WIN_SERVER_BOX"] || "gusztavvargadr/windows-server-2022-standard"
  CLIENT_BOX = ENV["TDM_WIN_CLIENT_BOX"] || "gusztavvargadr/windows-11"
  DOMAIN = "durand.lan"
  NETBIOS = "DURAND"
  PROVISION = File.join(__dir__, "provision")

  def self.lab(config, dir)
    lab = Lab.new(config, dir)
    yield lab
    lab
  end

  # Paire de clés RSA propre au lab, dans <lab>/.tdm (créée au premier `vagrant up`, conservée ensuite).
  def self.ssh_key(dir)
    folder = File.join(dir, ".tdm")
    key = File.join(folder, "id_rsa")
    pub = key + ".pub"
    unless File.exist?(key) && File.exist?(pub)
      FileUtils.mkdir_p(folder)
      rsa = OpenSSL::PKey::RSA.new(3072)
      File.write(key, rsa.to_pem)
      File.chmod(0o600, key) rescue nil
      blob = ssh_string("ssh-rsa") + ssh_mpint(rsa.e) + ssh_mpint(rsa.n)
      File.write(pub, "ssh-rsa #{Base64.strict_encode64(blob)} tdm-lab\n")
    end
    [key, File.read(pub).strip]
  end

  def self.ssh_string(bytes)
    [bytes.bytesize].pack("N") + bytes.b
  end

  def self.ssh_mpint(bn)
    bytes = bn.to_s(2)
    bytes = "\x00".b + bytes if bytes.getbyte(0) >= 0x80
    ssh_string(bytes)
  end

  class Lab
    attr_reader :name

    def initialize(config, dir)
      @config = config
      @dir = dir
      @name = File.basename(dir)
      @count = 0
      @key, pub = TDM.ssh_key(dir)
      @pub_b64 = Base64.strict_encode64(pub)
      config.vm.box_check_update = false
      config.vm.synced_folder ".", "/vagrant", disabled: true
      config.ssh.username = "vagrant"
      config.ssh.private_key_path = @key
      config.ssh.insert_key = false
    end

    def server(name, **opts)
      machine(name, SERVER_BOX, **opts)
    end

    def client(name, **opts)
      machine(name, CLIENT_BOX, **{ memory: 3072 }.merge(opts))
    end

    # Options : hostname (obligatoire), ip/prefix/gateway/dns (carte LAN ; ip: nil = non configurée),
    # memory, cpus, primary, domain: :forest (promeut un contrôleur du domaine durand.lan),
    # join: true (joint le poste au domaine), scenario: "scenario.ps1" (script du lab, relatif au dossier).
    def machine(name, box, hostname:, ip: nil, prefix: 24, gateway: nil, dns: nil, memory: 2048, cpus: 2,
                primary: false, domain: nil, join: false, scenario: nil)
      @count += 1
      mac = format("080027AA%02X%02X", @name.sum % 256, @count)
      @config.vm.define name, primary: primary do |m|
        m.vm.box = box
        m.vm.hostname = hostname
        m.vm.guest = :windows
        m.vm.communicator = "winrm"
        m.winrm.username = "vagrant"
        m.winrm.password = "vagrant"
        m.winrm.retry_limit = 60
        m.winrm.retry_delay = 10
        m.vm.boot_timeout = 1200
        m.vm.graceful_halt_timeout = 300
        m.vm.network :forwarded_port, guest: 22, host: 2222, host_ip: "127.0.0.1", id: "ssh", auto_correct: true
        m.vm.network :forwarded_port, guest: 3389, host: 33389, host_ip: "127.0.0.1", id: "rdp", auto_correct: true
        m.vm.network :private_network, ip: ip || "192.168.10.250", auto_config: false,
                     virtualbox__intnet: "tdm-#{@name}", mac: mac
        m.vm.provider "virtualbox" do |vb|
          vb.name = "TDM-#{@name}-#{name}"
          vb.memory = memory
          vb.cpus = cpus
          vb.linked_clone = true
          vb.gui = false
          vb.customize ["modifyvm", :id, "--vram", "128"]
        end

        args = ["-PublicKeyB64", @pub_b64, "-LanMac", mac.scan(/../).join("-")]
        args += ["-LanIp", ip, "-Prefix", prefix.to_s] if ip
        args += ["-Gateway", gateway] if gateway
        args += ["-Dns", dns] if dns
        m.vm.provision "tdm-base", type: "shell", path: File.join(PROVISION, "base.ps1"), args: args

        if domain == :forest
          m.vm.provision "tdm-ad-foret", type: "shell", path: File.join(PROVISION, "ad-forest.ps1"),
                                         args: ["-Domain", DOMAIN, "-Netbios", NETBIOS], reboot: true
          m.vm.provision "tdm-ad-pret", type: "shell", path: File.join(PROVISION, "ad-ready.ps1"),
                                        args: ["-Domain", DOMAIN]
        end
        if join
          m.vm.provision "tdm-jonction", type: "shell", path: File.join(PROVISION, "join-domain.ps1"),
                                         args: ["-Domain", DOMAIN, "-Netbios", NETBIOS], reboot: true
        end
        if scenario
          m.vm.provision "tdm-scenario", type: "shell", path: File.join(@dir, scenario)
        end
      end
    end
  end
end
