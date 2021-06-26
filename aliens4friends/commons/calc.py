import numpy

class Calc:

	@staticmethod
	def levenshtein(first, second):

		dist = numpy.zeros((len(first) + 1, len(second) + 1))

		# start values
		for f in range(len(first) + 1):
			dist[f][0] = f

		for s in range(len(second) + 1):
			dist[0][s] = s

		insert = 0
		delete = 0
		replace = 0

		for f in range(1, len(first)+1):
			for s in range(1, len(second)+1):
				if (first[f-1] == second[s-1]):
					dist[f][s] = dist[f-1][s-1]
				else:
					insert = dist[f][s-1]
					delete = dist[f-1][s]
					replace = dist[f-1][s-1]

					if (insert <= delete and insert <= replace):
						dist[f][s] = insert+1
					elif (delete <= insert and delete <= replace):
						dist[f][s] = delete+1
					else:
						dist[f][s] = replace+1

		res = dist[len(first)][len(second)];

		return res
