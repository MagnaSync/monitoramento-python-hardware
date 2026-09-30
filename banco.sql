
CREATE DATABASE magnasync_1;
USE magnasync_1;

CREATE TABLE usuario (
    id_usuario INT PRIMARY KEY AUTO_INCREMENT,
    nome VARCHAR(45) NOT NULL,
    nome_social VARCHAR(45),
    email VARCHAR(45) NOT NULL,
    telefone VARCHAR(20) NOT NULL,
    cpf CHAR(11) NOT NULL,
    cargo VARCHAR(45)
);

CREATE TABLE hospital (
    id_hospital INT PRIMARY KEY AUTO_INCREMENT,
    id_usuario INT NOT NULL,
    nome VARCHAR(100) NOT NULL,
    cnpj CHAR(14),
    cep CHAR(9),
    rua VARCHAR(45),
    cidade VARCHAR(45),
    estado CHAR(2),
    telefone VARCHAR(45),
    codigo_hospital VARCHAR(10) NOT NULL,
    CONSTRAINT fk_hospital_usuario FOREIGN KEY (id_usuario)
        REFERENCES usuario(id_usuario)
);

CREATE TABLE equipamento (
    id_equipamento INT PRIMARY KEY AUTO_INCREMENT,
    id_hospital INT NOT NULL,
    modelo VARCHAR(100) NOT NULL,
    fabricante VARCHAR(60),
    mac_address VARCHAR(60),
    sistema_operacional VARCHAR(60),
    status_atual VARCHAR(45),
    data_instalacao DATE,
    CONSTRAINT fk_equipamento_hospital FOREIGN KEY (id_hospital)
        REFERENCES hospital(id_hospital)
);

CREATE TABLE registros (
    id_registro INT PRIMARY KEY AUTO_INCREMENT,
    id_equipamento INT NOT NULL,

    cpu_percentual DECIMAL(5,2),
    cpu_frequencia DECIMAL(10,2),
    cpu_nucleos INT,
    cpu_status VARCHAR(10),            

    ram_percentual DECIMAL(5,2),
    ram_total DECIMAL(10,2),           
    ram_disponivel DECIMAL(10,2),      
    ram_status VARCHAR(10),

    disco_percentual DECIMAL(5,2),
    disco_total DECIMAL(10,2),         
    disco_disponivel DECIMAL(10,2),    
    disco_status VARCHAR(10),

    download_mb DECIMAL(12,1),       
    upload_mb DECIMAL(12,1),          

    status_geral VARCHAR(10),          
    data_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_registros_equipamento FOREIGN KEY (id_equipamento)
        REFERENCES equipamento(id_equipamento)
);

CREATE TABLE alerta (
    id_alerta INT PRIMARY KEY AUTO_INCREMENT,
    id_equipamento INT NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    descricao VARCHAR(255),
    valor_atual DECIMAL(10,2),
    limite DECIMAL(10,2),
    data_hora DATETIME NOT NULL,
    status_atual VARCHAR(20),
    CONSTRAINT fk_alerta_equipamento FOREIGN KEY (id_equipamento)
        REFERENCES equipamento(id_equipamento)
);

SELECT * FROM equipamento;
SELECT * FROM registros;