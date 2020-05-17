# -*- coding: utf-8 -*-
"""ProjetFinal_b3.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Vrojn-guAFfaTS8Wl-OAArTWV-O0pN1C

# Introduction 
This program is a neuronal newtork which can increase (7 by 7) images to (28 by 28) while keeping the global shape described by the starting image.

*   The specificity here is the loss function which has been developped by ourself. The custom loss function returns the result of the addition of the super SuperResolutionModel loss and a classification loss obtained by feeding an MNIST classifier with the output of SuperResolutionModel.

First we have to import all the libraries that we need
"""

import torch
import matplotlib.pyplot as plt
import torch.nn as nn
import torch.nn.functional as F
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
from torch.utils.data import TensorDataset
import torch.optim as optim
from torch.optim import lr_scheduler
from skimage.measure import block_reduce
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.image import imread

"""This cell allows to dowload the MNIST dataset. 
We apply a modification on the content by the transform "mnist_transform" which is a transformation of all images to tensors. That is these tensors that we will use to train our model.

Then we create two dataloader :

*   The first one, train_loader is made from the train dataset of MNIST.
*   The second one, test_loader is made from the test dataset of MNIST.

Our train_loader and test_loader are composed by batchs of 32 images .
"""

mnist_transform = transforms.Compose([
  transforms.ToTensor()
])

train_dataset = datasets.MNIST(root = '../data', train = True, download = True, transform = mnist_transform)
test_dataset = datasets.MNIST(root = '../data', train = False, download = True, transform = mnist_transform)

train_loader = DataLoader(train_dataset, batch_size = 32, shuffle = True)
test_loader  = DataLoader(test_dataset, batch_size = 32, shuffle = True)

"""The following cell creates a dataset composed by minimized images (From 28x28 to 7x7) by using an average pooling operation on our train and test datasets (based on the FashionMNIST dataset) to keep the global shape of the pattern on each image. 

Then we initialise two loader based on our new datasets, new_train_dataset and new_test_dataset.
"""

def get_minimized_dataset(dataset):
  new_dataset = []
  for i_data in range(len(dataset)):
    new_dataset.append([])
    new_dataset[i_data].append(torch.tensor([block_reduce(dataset[i_data][0][0], block_size = (4,4), func=np.mean)]))
    new_dataset[i_data].append(dataset[i_data][0])
    new_dataset[i_data].append(dataset[i_data][1])
  return new_dataset

new_train_dataset = get_minimized_dataset(train_dataset)
new_test_dataset = get_minimized_dataset(test_dataset)

new_train_loader = DataLoader(new_train_dataset, batch_size = 32, shuffle = True)
new_test_loader = DataLoader(new_test_dataset, batch_size = 32, shuffle = True)

"""This class defines a convolutional block which will be implemented in our model.
By default this block does not changes the input size and a relu activation function is applied.
"""

class ConvBlock(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size = 3, stride = 1, padding = 1, act = F.relu):
        super(ConvBlock, self).__init__()
        self.conv = nn.Conv2d(
            in_channels  = in_channels, #nb de chanels entrantes (3) si c'est une image
            out_channels = out_channels, #nb de chanels sortantes, de formes differntes à capter du coup
            kernel_size  = kernel_size, #taille du kernel (matrice)
            stride       = stride,  #de combiens de pixels le kernel est decalé pendant les operations
            padding      = padding, #nb pixels hors du cadre
        )
        self.act = act

    def forward(self, x):
        x = self.conv(x)
        x = self.act(x)
        return x

"""This class defines a convolutional upsample which will be usefull to increase by 2 the size of our images in our neuronal network."""

class ConvUpsample(nn.Module):

    def __init__(self, kernel_size = 3, stride = 1, padding = 0, act = F.relu):
        super(ConvUpsample, self).__init__()   
        self.conv = nn.Upsample(scale_factor = 2, mode='bilinear', align_corners=False)

    def forward(self, x):
        x = self.conv(x)
        return x

"""This class defines a classifier neuronal network which can predict a class of an image between 0 and 9.
It uses several convolutional layer and then several linear layer to detect what number each image represents.
"""

class Classifier(nn.Module):
    def __init__(self):
        super(Classifier, self).__init__()

        self.conv_layers = nn.Sequential(
            ConvBlock(1, 32),
            nn.Dropout2d(0.2),
            ConvBlock(32, 64),
            nn.Dropout2d(0.1)
        )
            
        self.dropout1 = nn.Dropout2d(0.2)
        self.dropout2 = nn.Dropout2d(0.1)
        self.linear1 = nn.Linear(64 * 14 * 14, 64)
        self.linear3 = nn.Linear(64, 10)


    def forward(self, x):
        x = self.conv_layers(x)
        x = F.max_pool2d(x, 2)
        x = x.view(-1, 14 * 14 * 64)
        x = self.linear1(x)
        x = F.relu(x)
        x = self.linear3(x)
        output = F.log_softmax(x, dim = 1)
        return output

"""The MNISTClassifier class creates a classifier neuronal network on the MNIST dataset.

The model can be trained and frozen to be used by another program or neuronal network without modifying his weights.
"""

class MNISTClassifier():
    def __init__(self):
      self.model = Classifier()
      self.trained = False

    def get_model(self):
      return self.model

    def freeze_model(self):
      if (not self.trained):
        raise Exception("Please train model before freezing it")
      for param in self.model.parameters():
        param.requires_grad = False

    def __train_loop(self, model, criterion, optimizer, train_loader, test_loader, epochs, batch_size, device):
        for epoch in range(epochs):
            for batch_id, (X, y) in enumerate(train_loader):
                X = X.to(device)
                y = y.to(device)
                y_pred = model(X)
                loss   = criterion(y_pred, y) 
                loss.backward()
                optimizer.step()
                optimizer.zero_grad()
            print(f'{100 * self.__evaluation_loop(model, train_loader, test_loader, batch_size, device):5.3f}% accuracy')
            

    def __evaluation_loop(self, model, train_loader, test_loader, batch_size, device):
        correct_pred = 0
        total_pred   = 0
        with torch.no_grad():
            for batch_id, (X, y) in enumerate(test_loader):
                X = X.to(device)
                y = y.to(device)
                if(batch_id == 200):
                  break
                y_pred        = model(X)
                y_pred_class  = y_pred.argmax(dim = 1)
                correct_pred += (y_pred_class == y).sum().item()
                total_pred   += len(y)
        return correct_pred / total_pred

    def train(self, epochs = 20, batch_size = 32, learning_rate = 1e-3, freezed=False):
        epochs        = 8
        batch_size    = 32
        learning_rate = 1e-3
        device = torch.device('cuda')
        self.model.to(device) 
        criterion     = nn.NLLLoss()
        optimizer     = optim.SGD(params = self.model.parameters(), lr = learning_rate)
        self.__train_loop(self.model, criterion, optimizer, train_loader, test_loader, epochs, batch_size, device)
        self.trained = True

"""This is our custom loss function. It returns the result of the SuperResolutionModel loss and the MNISTClassifier loss with the SuperResolutionModel prediction used as input."""

def lossefunction(imageprediction, classifierprediction, imagegoal, numgoal):
  f1 = nn.NLLLoss()
  classifier_loss = f1(classifierprediction, numgoal)
  f2 = nn.MSELoss()
  model_loss = f2(imageprediction, imagegoal)
  return model_loss + classifier_loss

"""The goal of our model is to increase the resolution of a given image while increase the quality of the pattern described by the image.

This model is composed by several convolution layer and performs two increase operation (from 7 * 7 to 14 * 14 and from 14 * 14 to 28 * 28).

It uses some dropout to avoid dataset memorizing from model.
"""

class SuperResolutionModel(nn.Module):
    def __init__(self):
        super(SuperResolutionModel, self).__init__()

        self.seq = nn.Sequential(
            ConvUpsample(),
            ConvBlock(1, 128),
            ConvBlock(128, 128),
            nn.Dropout(p = 0.2),
            ConvBlock(128, 64),
            ConvUpsample(),
            ConvBlock(64, 64),
            nn.Dropout(p = 0.1),
            ConvBlock(64, 32),
            ConvBlock(32, 32),
            ConvBlock(32, 1, act = nn.Sigmoid())
        )
        classifier = MNISTClassifier()
        classifier.train(freezed = True)
        self.MNISTclassifier = classifier.get_model()

    def forward(self, x):
        imageprediction = self.seq(x)
        classifier_pred = self.MNISTclassifier(imageprediction)
        return imageprediction, classifier_pred

"""This method allows to train our model. It calculates a prediction, and adjust the weights according to the result.

At each epoch we call the evaluation function to know the model accuracy.
"""

def train(model, criterion, optimizer, epochs, trainloader, testloader, device, scheduler): 
    model.train() 
    for epoch in range(epochs): 
        print('Epoch {}/{}'.format(epoch+1, epochs))
        print('-' * 10)
        eval_loss  = evaluate(model, criterion, device, testloader, 20)
        print(f' Eval : loss {eval_loss:6.7f} 'f'\n')
        for batch_id, (X, y, z) in enumerate(trainloader): #X = data given to the model for predictions , y = the expected result, z = int representation of the image
            X, y, z = X.to(device), y.to(device), z.to(device) #64 images 28x28
            optimizer.zero_grad() #pour "nettoyer" l'optimiser
            model_pred, classifier_pred = model(X) #gets the model prediction
            loss = lossefunction(model_pred, classifier_pred, y, z) #calculates the prediction loss
            loss.backward() #updates the weights to make future predictions closer to what we want 
            optimizer.step() #notifies the optimizer that we did a step 
        scheduler.step() #decreases the learning rate

"""This method goal is to evaluate the model accuracy. For each batch in the loader,
it calculates the model prediction on an element and use the criterion for calculate the gap between the prediction and the desired result. This result is added to the loss.
When n_batch have been calculated, the method shows 4 images :

*   The first one is the image that has been given to the model.
*   The second one is the desired image.
*   The last one is the image made by the model.


Finally the function returns the average loss of all predictions.
"""

def evaluate(model, criterion, device, loader, n_batch = -1):
    model.eval()
    losses = 0
    total_pred = 0
    figure = plt.figure()
    with torch.no_grad():
      for batch_id, (X, y, z) in enumerate(loader):
            X = X.to(device)
            y = y.to(device)
            z = z.to(device)
            if (batch_id == n_batch): 
              figure.add_subplot(1, 3, 1)
              plt.imshow(X[0][0].cpu().detach(), cmap = 'gray')
              figure.add_subplot(1, 3, 2)
              plt.imshow(y[0][0].cpu().detach(), cmap = 'gray')
              figure.add_subplot(1, 3, 3)
              img, pred = model(X)
              plt.imshow(img[0][0].cpu().detach(), cmap = 'gray')
              plt.show()
              return losses / total_pred
            model_pred, classifier_pred = model(X)
            losses += lossefunction(model_pred, classifier_pred, y, z)
            total_pred  += len(y)

def main():
    epochs        = 8 #number of detabase iteration
    learning_rate = 1e-3 #sets the starting learning rate
    device = torch.device('cuda') #sets the device to the GPU
    model = SuperResolutionModel() #creates the neuronal network
    model = model.to(device) #sets the model in the device
    optimizer     = optim.Adagrad( params = model.parameters(), lr = learning_rate )#setting the optimizer algorithm with wich update neuronal weights
    scheduler = lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.3)#the scheduler is used to update the learning rate gradually
    criterion     = nn.MSELoss() #sets the loss function
    train(model, criterion, optimizer, epochs, new_train_loader, new_test_loader, device, scheduler)
    return

main()