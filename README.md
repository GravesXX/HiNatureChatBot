# HiNature ChatBot

HiNature ChatBot is an AI-powered assistant built for **Hi Nature Pet**, designed to enhance customer communication by providing instant responses to common inquiries. The chatbot integrates seamlessly with Shopify and AWS services to deliver accurate, reliable, and scalable customer support.


## ✨ Features

- **Order Status Tracking** – Customers can easily check the status of their orders.  
- **Delivery Inquiries** – Provides updates and information about delivery schedules.  
- **Meal Calculation** – Helps pet owners calculate recommended meal portions based on their pet’s details.  
- **Company FAQs & Background** – Shares company information and answers common questions automatically.  



## 🛠️ Technical Stack

The project leverages a modern cloud-native architecture with the following technologies:

### **Frontend**
- **JavaScript** for chatbot interface logic.  
- **Shopify Liquid** templates for seamless integration into the online store.  

### **Backend / Cloud**
- **AWS Lambda** for serverless function execution.  
- **Amazon API Gateway** to expose REST APIs.  
- **Amazon DynamoDB** for storing customer sessions and conversation data.  
- **Amazon Cognito** for secure authentication.  
- **Amazon SQS** for handling asynchronous workloads.  
- **Amazon S3 + CloudFront** for hosting and distributing chatbot assets.  
- **Amazon Fargate** for scalable load testing.  
- **Amazon CloudWatch** for logging and monitoring.  
- **Amazon ECR** for container image storage.  

## AWS Technical Architecture Diagram
Below is the architecture diagram showing how AWS services are integrated to power HiNature ChatBot:

<img width="1830" height="1320" alt="Blank diagram" src="https://github.com/user-attachments/assets/a20eaf66-a085-4411-834d-3a0c7f560805" />

## 💬 Demo Use Cases
### i) Conversation Context Handling
Demonstrates how the chatbot maintains **context awareness** throughout the conversation.  

<p align="center">
  <img width="344" height="538" alt="context" src="https://github.com/user-attachments/assets/c20a75ec-440a-465d-83c8-0ae5e8e08ad2" />
</p>

---

### ii) Order Status (Fulfilled Order)
Shows how the chatbot retrieves and responds with **order details** when a valid order exists.  

<p align="center">
  <img width="364" height="549" alt="with_order" src="https://github.com/user-attachments/assets/26abdd3c-0c42-4ae6-8092-c73b043cd50d" />
</p>

---

### iii) Order Status (No Fulfilled Order)
Illustrates the chatbot response when **no fulfilled order** is found in the system.  

<p align="center">
  <img width="334" height="519" alt="no_order" src="https://github.com/user-attachments/assets/e084bb06-6520-41c1-b972-0e9a7714c802" />
</p>

---

### iv) User Not Found
Demonstrates how the chatbot gracefully handles cases where the **user does not exist** in the database.  

<p align="center">
  <img width="342" height="525" alt="user_DNE" src="https://github.com/user-attachments/assets/5afffa2a-8de9-4230-8254-1842f550cc8c" />
</p>

---

## 🚀 Future Improvements
- Expand intent coverage with additional FAQs and personalized recommendations.  
- Integrate multilingual support for broader accessibility.  
- Add analytics to better understand customer interactions.  
- Deploy improved meal calculator using ML for more accurate recommendations.  

---

## 📌 About Hi Nature Pet
[Hi Nature Pet](https://hinaturepet.com/) provides fresh, high-quality meals for pets, ensuring balanced nutrition with natural ingredients. The chatbot project is part of their initiative to improve **customer engagement and automation**.  
