# This file Train a word Embedding Using SkipGram
# Implementing refer to official tutorial of pytorch
# https://pytorch.org/tutorials/beginner/nlp/word_embeddings_tutorial.html
# TODO Add subsampling and negative sampling

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchtext.datasets import WikiText2
from torch.utils.data import Dataset, DataLoader
from collections import Counter
from nltk.tokenize import word_tokenize
from tqdm import tqdm
from tensorboardX import SummaryWriter
from utils import print_k_nearest_neighbour
# download WikiText2
# WikiText2.download('./corpus')

class WikiText2DataSet(Dataset):
    """
    We are just training word embeddings, what we need is just text,
    And thus we do not perform train, val, test splitting and sort of
    things. You can change the data file to whatever you want as long
    as it's plain text, and it's not that big.
    It's toy implementation, train on rather small dataset,
    so we don't restrict vocabulary size.
    """
    def __init__(self, data_file_path, window_size=2):
        """
        :param data_file_path: path for the plain text file
        :param ngram:  language model n-grams
        """
        with open(data_file_path,'r',encoding='utf-8') as f:
            s = f.read().lower()
        words_tokenized = word_tokenize(s)
        # pairs
        self.word_pair = [(words_tokenized[i], words_tokenized[i+j]) for j in range(-window_size, window_size + 1) if j != 0 \
                                for i in range(window_size, len(words_tokenized)-window_size)]

        self.vocab = Counter(words_tokenized)
        self.word_to_idx = {word_tuple[0]: idx for idx, word_tuple in enumerate(self.vocab.most_common())}
        self.vocab_size = len(self.vocab)
        self.window_size = window_size

    def __getitem__(self, idx):
        context = torch.tensor([self.word_to_idx[self.word_pair[idx][0]]])
        target = torch.tensor([self.word_to_idx[self.word_pair[idx][1]]])
        return context, target

    def __len__(self):
        return len(self.word_pair)

class SkipGram(nn.Module):

    def __init__(self, vocab_size, embedding_dim, window_size):
        super(SkipGram, self).__init__()
        self.embeddings = nn.Embedding(vocab_size, embedding_dim)
        self.linear = nn.Linear(embedding_dim, vocab_size)
        self.window_size = window_size

    def forward(self, inputs):
        embeds = torch.sum(self.embeddings(inputs), dim=1)  # [200, 1, 50] => [200, 50]
        # embeds = self.embeddings(inputs).view((batch_size, -1))
        out = self.linear(embeds)  # nonlinear + projection
        log_probs = F.log_softmax(out, dim=1)  # softmax compute log probability

        return log_probs


WINDOW_SIZE = 2
EMBEDDING_DIM = 50
BATCH_SIZE = 800
NUM_EPOCH = 5

# I think torchtext is really hard to use
# It's a toy example, so you can use any plain text dataset
data_file_path = '/home/fuchs/Documentos/MESTRADO/Masters/Code/pytorch-word-embedding-master/corpus/Pride-and-Prejudice.txt'
# data_file_path = './corpus/Pride-and-Prejudice.txt'

data = WikiText2DataSet(data_file_path=data_file_path)
model = SkipGram(len(data.vocab), EMBEDDING_DIM, WINDOW_SIZE)
# optimizer = optim.SGD(model.parameters(), lr=0.001)
optimizer = optim.Adam(model.parameters(), lr=0.01)
loss_function = nn.MSELoss()
losses = []
cuda_available = torch.cuda.is_available()
data_loader = DataLoader(data, batch_size=BATCH_SIZE)

# Writer
writer = SummaryWriter('./logs/NNLM')

for epoch in range(NUM_EPOCH):
    total_loss = 0
    for context, target in tqdm(data_loader):
        # context: torch.Size([10, 4])
        # target:  torch.Size([10, 1])
        if context.size()[0] != BATCH_SIZE:
            continue
        # deal with last several batches

        if cuda_available:
            context = context.cuda()
            target = target.squeeze(1).cuda()
            model = model.cuda()

        model.zero_grad()
        log_probs = model(context)
        loss = loss_function(log_probs, target)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    losses.append(total_loss)
    writer.add_scalar('Train/Loss', total_loss, epoch)

    # TODO add visualization of embedding
    # writer.add_embedding(model.embeddings.weight, metadata=data.word_to_idx.keys(), global_step=epoch)
    # It should work, but unfortunately not. see this issue, it seems like a tensorboard 1.11.0's
    # https://github.com/tensorflow/tensorboard/issues/1480

    print('total_loss:',total_loss)

writer.close()

# print some results
embed_matrix = model.embeddings.weight.detach().cpu().numpy()
print_k_nearest_neighbour(embed_matrix, data.word_to_idx['she'], 5, list(data.word_to_idx.keys()))
print_k_nearest_neighbour(embed_matrix, data.word_to_idx['is'], 5, list(data.word_to_idx.keys()))
print_k_nearest_neighbour(embed_matrix, data.word_to_idx['good'], 5, list(data.word_to_idx.keys()))